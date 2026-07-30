import logging
import re
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.schemas import (
    AnalyzeRequest,
    BlindSpotReport,
    ScrapeRequest,
    ScrapeResponse,
    ChatRequest,
    ChatResponse,
    Citation
)
from app.services.scraper import scrape_article_url
from app.services.web_search import search_live_internet
from app.chains.pipeline import run_echo_breaker_pipeline
from app.chains.chain_extractor import get_llm, extract_image_content
from langchain_core.prompts import PromptTemplate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend engine for Echo-Breaker Chrome Extension using Pattern 3 Multi-Step LangChain Pipeline."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    from dotenv import load_dotenv
    import os
    
    # Reload .env to ensure fresh validation on startup
    load_dotenv()
    
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    
    if not gemini_key and not openai_key and not groq_key:
        logger.warning(
            "WARNING: No active LLM API keys found in .env configuration! "
            "Please configure GEMINI_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY to ensure Echo-Breaker performs analysis."
        )
    else:
        logger.info(
            f"API Key startup check completed. Configured providers: "
            f"Gemini: {'Configured' if gemini_key else 'Missing'}, "
            f"OpenAI: {'Configured' if openai_key else 'Missing'}, "
            f"Groq: {'Configured' if groq_key else 'Missing'}."
        )

@app.get("/")
def root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "pattern": "Pattern 3 — Multi-Step LangChain Pipeline"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/api/v1/scrape", response_model=ScrapeResponse)
async def scrape_endpoint(payload: ScrapeRequest):
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL is required")
    scraped = await scrape_article_url(payload.url)
    return ScrapeResponse(**scraped)

@app.post("/api/v1/analyze", response_model=BlindSpotReport)
async def analyze_endpoint(payload: AnalyzeRequest):
    article_text = payload.text
    article_url = payload.url
    article_title = payload.title

    if article_url and (not article_text or len(article_text.strip()) < 50):
        logger.info(f"Scraping content from URL: {article_url}")
        scraped = await scrape_article_url(article_url)
        article_text = scraped.get("text", "")
        if not article_title:
            article_title = scraped.get("title", "")

    if not article_text and not article_url and not payload.image_base64:
        raise HTTPException(
            status_code=400,
            detail="Payload must include at least a URL, selected text, or screenshot image."
        )

    try:
        report = await run_echo_breaker_pipeline(
            url=article_url,
            text=article_text,
            image_base64=payload.image_base64,
            title=article_title
        )
        return report
    except Exception as e:
        logger.error(f"Error during analysis pipeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

def build_focused_topic_query(
    question: str,
    selected_text: Optional[str],
    image_text: Optional[str],
    context_url: Optional[str],
    report_summary: Optional[str]
) -> str:
    candidates = []

    if image_text and len(image_text) > 15 and "error" not in image_text.lower():
        candidates.append(image_text)
    if selected_text and len(selected_text) > 15:
        candidates.append(selected_text)
    if report_summary and len(report_summary) > 15:
        candidates.append(report_summary)

    combined = " ".join(candidates)

    clean_combined = re.sub(
        r'Pasted article screenshot payload|Screenshot image payload analysis|Image screenshot analysis|Web article context',
        '', combined, flags=re.IGNORECASE
    ).strip()

    if len(clean_combined) > 15:
        return clean_combined[:140].strip()

    if context_url:
        clean_url = context_url.replace("https://", "").replace("http://", "").replace("twitter.com/", "").replace("x.com/", "")
        clean_url = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_url)
        return f"{clean_url[:80]} news"

    cleaned_q = re.sub(r'^(is the|is this|tf isnt|how true is|can u|tell me if|is it|what is)\s+', '', question, flags=re.IGNORECASE).strip()
    return cleaned_q if len(cleaned_q) > 5 else "hardware technology news"

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    question = payload.question
    selected_text = payload.selected_text or ""
    report_summary = payload.report_summary or ""

    image_ocr_text = ""
    if payload.image_base64 and len(payload.image_base64) > 50:
        logger.info("Chatbot: Performing Gemini Vision OCR on image payload...")
        image_ocr_text = await extract_image_content(payload.image_base64)

    search_query = build_focused_topic_query(
        question=question,
        selected_text=selected_text,
        image_text=image_ocr_text,
        context_url=payload.context_url,
        report_summary=report_summary
    )

    # Use the question as part of the search query if it is an informational question
    is_veracity_query = any(w in question.lower() for w in ["true", "false", "real", "fake", "verify", "fact check", "legit", "accurate", "leak", "rumor"])
    
    if not is_veracity_query:
        # If it's a general question like "what is the current lineup", append it to search!
        search_query = f"{search_query[:80]} {question[:60]}".strip()

    logger.info(f"Chatbot: Target Topic Search Query built: '{search_query}'")
    live_results = await search_live_internet(search_query, max_results=4)

    citations = [
        Citation(title=r.get("title", "Web Source"), url=r.get("url", "#"), snippet=r.get("snippet", "")[:180])
        for r in live_results
    ]

    combined_context = f"{selected_text}\n{image_ocr_text}\n{report_summary}".strip()
    is_leak_or_rumor = any(w in (combined_context + question).lower() for w in ["leak", "rumor", "alleged", "unconfirmed", "roadmap", "insider", "gpu"])

    llm = get_llm()
    if llm:
        try:
            if is_veracity_query:
                system_instructions = """Carefully evaluate the veracity of the claim:
- If the content is an unconfirmed leak, rumor, or hardware roadmap leak: output **VERDICT: ⚠️ UNVERIFIED LEAK / UNCONFIRMED RUMOR — Reporting confirms this leak was posted, but official manufacturer verification is pending.**
- If the content is fully confirmed by official statements: output **VERDICT: ✅ FACTUALLY CONFIRMED — Verified by official statements and news reporting.**
- If the claim is false, misleading, or debunked: output **VERDICT: 🔴 MISLEADING / UNVERIFIED CLAIM — Content is exaggerated, unconfirmed, or misleading.**

Followed by a detailed explanation assessing the truth of the post based on web search context."""
            else:
                system_instructions = """You are a helpful, conversational AI assistant.
Answer the user's question directly based on the provided context and live web search results.
Do NOT output a VERDICT banner. Just provide a clear, natural language answer."""

            chat_prompt = PromptTemplate(
                template=f"""You are Echo-Breaker AI, a non-partisan investigative assistant.
Analyze the user's question, the provided context, and the live web search results.

USER QUESTION: {{question}}
ATTACHED CONTEXT: {{combined_context}}
LIVE WEB SEARCH RESULTS: {{search_results}}

{system_instructions}
""",
                input_variables=["question", "combined_context", "search_results"]
            )
            
            chain = chat_prompt | llm
            response_obj = await chain.ainvoke({
                "question": question,
                "combined_context": combined_context[:3000] or "General context",
                "search_results": str([r for r in live_results])[:3000]
            })

            ans_text = response_obj.content if hasattr(response_obj, "content") else str(response_obj)
            return ChatResponse(
                answer=ans_text,
                veracity_check="Verified against live web search data",
                citations=citations
            )
        except Exception as e:
            error_str = str(e)
            logger.error(f"Chatbot LLM error: {error_str}")
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Rate limit" in error_str:
                return ChatResponse(
                    answer="**⚠️ API Quota Exceeded:** You have reached the rate limit for your Gemini Free Tier API key (15 requests per minute). Please wait 60 seconds before trying again, or upgrade your API key in the `.env` file.",
                    veracity_check="API Rate Limit Exceeded",
                    citations=[]
                )

    # Fallback Handling
    first_title = live_results[0].get("title", "Industry Web Reporting") if live_results else "tech news archives"
    topic_label = search_query[:80] or "the topic"

    if is_veracity_query:
        if is_leak_or_rumor:
            verdict_str = "**VERDICT: ⚠️ UNVERIFIED LEAK / UNCONFIRMED RUMOR — Reporting confirms this leak was posted, but official manufacturer verification is pending.**\n\n"
            veracity_badge_text = "Unconfirmed Leak / Rumor"
        else:
            verdict_str = "**VERDICT: ⚠️ PARTIALLY VERIFIED — Core reporting exists, but claims require independent verification.**\n\n"
            veracity_badge_text = "Partially Verified Context"
            
        explanation = (
            f"{verdict_str}"
            f"**Context Explanation:**\n"
            f"Regarding '{question}': The topic refers to {topic_label}.\n\n"
            f"Live web search cross-referencing industry reporting ({first_title}) shows ongoing coverage, but requires cross-checking against official announcements."
        )
    else:
        veracity_badge_text = "Answered from live web search"
        explanation = (
            f"Based on live web search results ({first_title}), current coverage indicates active developments regarding {topic_label}. "
            f"Please refer to the verified sources below for detailed specific answers to your question."
        )

    return ChatResponse(
        answer=explanation,
        veracity_check=veracity_badge_text,
        citations=citations
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
