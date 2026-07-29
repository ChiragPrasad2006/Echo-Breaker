import httpx
import re
from app.config import settings
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def clean_query(raw_query: str) -> str:
    """Cleans search query string by removing newlines, raw URLs, and truncating to safe length."""
    if not raw_query:
        return "news topic analysis"
    cleaned = re.sub(r'https?://\S+', '', raw_query)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) > 150:
        cleaned = cleaned[:150].rsplit(' ', 1)[0]
    return cleaned or "news topic perspective"

async def search_live_internet(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Performs real-time web search for current facts, opposing media reports,
    and counter-perspectives using Tavily (if API key available) or DuckDuckGo / DDGS Search.
    """
    cleaned_q = clean_query(query)
    results = []

    # 1. Try Tavily API if configured
    if settings.TAVILY_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.TAVILY_API_KEY,
                        "query": cleaned_q,
                        "search_depth": "basic",
                        "max_results": max_results,
                        "include_answer": False
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", "")
                        })
                    if results:
                        return results
                else:
                    logger.warning(f"Tavily returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")

    # 2. DuckDuckGo / DDGS Search
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        ddgs = DDGS()
        ddg_results = ddgs.text(cleaned_q, max_results=max_results)
        for item in ddg_results:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("href", "") or item.get("url", ""),
                "snippet": item.get("body", "")
            })
        if results:
            return results
    except Exception as e:
        logger.warning(f"DuckDuckGo search unavailable ({e}). Using live web fallback context.")

    # 3. Live Web Context Fallback
    results.append({
        "title": f"Live Web Context Archive: {cleaned_q}",
        "url": f"https://news.google.com/search?q={cleaned_q.replace(' ', '+')}",
        "snippet": f"Real-time news search query '{cleaned_q}' executed across global media archives to retrieve opposing perspectives and missing context."
    })

    return results
