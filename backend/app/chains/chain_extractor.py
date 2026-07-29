import json
import logging
from typing import Dict, Any, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.0-pro",
    "models/gemini-2.0-flash",
    "models/gemini-1.5-flash"
]

def get_llm():
    """Initializes LLM instance safely with fallback across supported Gemini and OpenAI models."""
    if settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            for model_name in GEMINI_MODELS:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model=model_name,
                        google_api_key=settings.GEMINI_API_KEY,
                        temperature=0.2
                    )
                    return llm
                except Exception as e:
                    logger.debug(f"Model {model_name} init failed: {e}")
        except Exception as e:
            logger.warning(f"Could not load ChatGoogleGenerativeAI: {e}")

    if settings.OPENAI_API_KEY:
        try:
            from langchain_community.chat_models import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.OPENAI_API_KEY,
                temperature=0.2
            )
        except Exception as e:
            logger.warning(f"Could not load ChatOpenAI: {e}")

    return None

async def extract_image_content(image_base64: str) -> str:
    """Uses multimodal LLM (Gemini Vision) to extract all text, tweets, and headlines from screenshot images."""
    llm = get_llm()
    if not llm or not image_base64:
        return "Screenshot image payload analysis"

    # Ensure clean data URL format
    image_data_url = image_base64 if image_base64.startswith("data:image") else f"data:image/png;base64,{image_base64}"

    try:
        from langchain_core.messages import HumanMessage
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "Extract all text, tweet contents, author name, claims, headlines, and main subject from this image screenshot in exact detail:"},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]
        )
        res = await llm.ainvoke([msg])
        extracted = res.content if hasattr(res, "content") else str(res)
        logger.info(f"Gemini Vision successfully extracted screenshot content: {extracted[:100]}...")
        return extracted
    except Exception as e:
        logger.error(f"Gemini Vision extraction error: {e}")
        return "Pasted article screenshot payload"

EXTRACTOR_PROMPT = """You are an expert news media analyst and investigative researcher.
Analyze the following news text, article content, tweet screenshot text, or user query to extract core facts, underlying narrative stance, and search queries for live internet verification.

SOURCE CONTENT:
{source_content}

URL / TITLE METADATA:
{metadata}

Respond ONLY with a valid JSON object matching this schema:
{{
    "core_topic": "Short title of the core event or topic",
    "primary_stance": "Summary of the article's explicit or implicit partisan stance or narrative lens",
    "key_claims": [
        "Claim 1 made in the text",
        "Claim 2 made in the text"
    ],
    "source_bias_indicator": "Description of framing (e.g. Left-leaning, Right-leaning, Anti-government, Pro-industry, Sensationalist, One-sided)",
    "search_queries": [
        "Specific news query 1 to search internet for opposing views",
        "Specific fact-check query 2 to search internet for missing facts"
    ]
}}
"""

async def run_chain_extractor(content: str, metadata: str = "") -> Dict[str, Any]:
    """Chain 1: Extract core topic, claims, framing, and live internet search queries."""
    llm = get_llm()
    if not llm:
        topic_preview = content[:80].replace("\n", " ").strip() or "News Article Analysis"
        return {
            "core_topic": topic_preview,
            "primary_stance": "Mainstream narrative framing",
            "key_claims": [content[:250].strip()],
            "source_bias_indicator": "Single Angle Perspective",
            "search_queries": [f"{topic_preview} opposing perspectives", f"{topic_preview} missing facts context"]
        }

    try:
        prompt = PromptTemplate(
            template=EXTRACTOR_PROMPT,
            input_variables=["source_content", "metadata"]
        )
        chain = prompt | llm | JsonOutputParser()
        result = await chain.ainvoke({
            "source_content": content[:6000],
            "metadata": metadata
        })
        return result
    except Exception as e:
        logger.error(f"Chain 1 Extractor error: {e}")
        topic_preview = content[:80].replace("\n", " ").strip() or "News Topic Analysis"
        return {
            "core_topic": topic_preview,
            "primary_stance": "Standard news reporting",
            "key_claims": [content[:250].strip()],
            "source_bias_indicator": "Partisan Framing",
            "search_queries": [f"{topic_preview} opposing views", f"{topic_preview} missing context"]
        }
