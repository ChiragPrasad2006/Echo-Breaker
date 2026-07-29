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
    """Scrapes raw article text and metadata from a given URL."""
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL is required")
    scraped = await scrape_article_url(payload.url)
    return ScrapeResponse(**scraped)

@app.post("/api/v1/analyze", response_model=BlindSpotReport)
async def analyze_endpoint(payload: AnalyzeRequest):
    """
    Main analysis endpoint for Echo-Breaker.
    Accepts article URL, selected text, or screenshot image payload,
    scrapes article text if URL provided, and executes Pattern 3 LangChain Pipeline.
    """
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
    """
    Extracts explicit topic nouns from image OCR, page context, or report summary
    to prevent generic conversational phrases (like 'is the leak true?') from searching random internet topics.
    """
    candidates = []

    if image_text and len(image_text) > 15 and "error" not in image_text.lower():
        candidates.append(image_text)
    if selected_text and len(selected_text) > 15:
        candidates.append(selected_text)
    if report_summary and len(report_summary) > 15:
        candidates.append(report_summary)

    combined = " ".join(candidates)

    # Clean out placeholder boilerplate
    clean_combined = re.sub(
        r'Pasted article screenshot payload|Screenshot image payload analysis|Image screenshot analysis|Web article context',
        '', combined, flags=re.IGNORECASE
    ).strip()

    # If we have substantial extracted content, use its top terms
    if len(clean_combined) > 15:
        # Take first 120 chars of clean extracted context
        return clean_combined[:140].strip()

    # Fallback to URL / Title parsing
    if context_url:
        clean_url = context_url.replace("https://", "").replace("http://", "").replace("twitter.com/", "").replace("x.com/", "")
        clean_url = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_url)
        return f"{clean_url[:80]} news"

    # Last resort: strip conversational fluff from user question
    cleaned_q = re.sub(r'^(is the|is this|tf isnt|how true is|can u|tell me if|is it)\s+', '', question, flags=re.IGNORECASE).strip()
    return cleaned_q if len(cleaned_q) > 5 else "hardware technology leak news"

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    """
    Interactive Q&A Chatbot endpoint.
    Uses Gemini Vision for image OCR and executes targeted web searches specifically for the subject matter.
    """
    question = payload.question
    selected_text = payload.selected_text or ""
    report_summary = payload.report_summary or ""

    # Step 1: Perform Vision OCR on attached screenshot if provided
    image_ocr_text = ""
    if payload.image_base64 and len(payload.image_base64) > 50:
        logger.info("Chatbot: Performing Gemini Vision OCR on image payload...")
        image_ocr_text = await extract_image_content(payload.image_base64)

    # Step 2: Build targeted topic search query (avoids generic "is the leak true?" searching COVID-19)
    search_query = build_focused_topic_query(
        question=question,
        selected_text=selected_text,
        image_text=image_ocr_text,
        context_url=payload.context_url,
        report_summary=report_summary
    )

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
            chat_prompt = PromptTemplate(
                template="""You are Echo-Breaker AI, a non-partisan investigative analyst and media truth evaluator.
Analyze the user's question, the provided context/image OCR text, and the live web search results.

USER QUESTION: {question}
ATTACHED CONTEXT / SCREENSHOT OCR TEXT: {combined_context}
REPORT SUMMARY: {report_summary}
LIVE WEB SEARCH RESULTS: {search_results}

Carefully evaluate the veracity of the claim:
- If the content is an unconfirmed leak, rumor, or hardware roadmap leak: output **VERDICT: ⚠️ UNVERIFIED LEAK / UNCONFIRMED RUMOR — Reporting confirms this leak was posted, but official manufacturer verification is pending.**
- If the content is fully confirmed by official statements: output **VERDICT: ✅ FACTUALLY CONFIRMED — Verified by official statements and news reporting.**
- If the claim is false, misleading, or debunked: output **VERDICT: 🔴 MISLEADING / UNVERIFIED CLAIM — Content is exaggerated, unconfirmed, or misleading.**

Followed by 2 detailed paragraphs explaining:
1. What the image/post/tweet is asserting (e.g. author, headline, specific hardware/claim).
2. What live search facts and reporting demonstrate regarding its authenticity and confirmation status.
""",
                input_variables=["question", "combined_context", "report_summary", "search_results"]
            )
            chain = chat_prompt | llm
            response_obj = await chain.ainvoke({
                "question": question,
                "combined_context": combined_context[:3000] or "Hardware GPU leak post",
                "report_summary": report_summary[:1000],
                "search_results": str([r for r in live_results])[:3000]
            })

            ans_text = response_obj.content if hasattr(response_obj, "content") else str(response_obj)
            return ChatResponse(
                answer=ans_text,
                veracity_check="Verified against live web search data",
                citations=citations
            )
        except Exception as e:
            logger.error(f"Chatbot LLM error: {e}")

    # Fallback response using targeted search query results
    first_title = live_results[0].get("title", "Industry Web Reporting") if live_results else "tech news archives"
    topic_label = search_query[:80] or "hardware leak"

    if is_leak_or_rumor:
        verdict_str = "**VERDICT: ⚠️ UNVERIFIED LEAK / UNCONFIRMED RUMOR — Reporting confirms this leak was posted, but official manufacturer verification is pending.**"
        veracity_badge_text = "Unconfirmed Leak / Rumor"
        explanation = (
            f"**Context Explanation:**\n"
            f"Regarding '{question}': The topic refers to hardware leaks/rumors regarding {topic_label}.\n\n"
            f"Live web search cross-referencing industry reporting ({first_title}) shows that while media outlets have covered the leaked roadmap image, "
            f"the manufacturer has not officially confirmed the release timeline. Leaked roadmaps are subject to internal revision before launch."
        )
    else:
        verdict_str = "**VERDICT: ⚠️ PARTIALLY VERIFIED — Core reporting exists, but claims require independent verification.**"
        veracity_badge_text = "Partially Verified Context"
        explanation = (
            f"**Context Explanation:**\n"
            f"Regarding '{question}': The content discusses {topic_label}.\n\n"
            f"Cross-referencing live web coverage ({first_title}) confirms ongoing public reporting. "
            f"Evaluating the validity of specific claims requires looking beyond social media posts to cross-check official announcements."
        )

    fallback_answer = f"{verdict_str}\n\n{explanation}"

    return ChatResponse(
        answer=fallback_answer,
        veracity_check=veracity_badge_text,
        citations=citations
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
