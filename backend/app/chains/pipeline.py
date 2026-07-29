import logging
from typing import Dict, Any, Optional
from app.chains.chain_extractor import run_chain_extractor, extract_image_content
from app.chains.chain_blindspot import run_chain_blindspot
from app.chains.chain_synthesizer import run_chain_synthesizer
from app.services.web_search import search_live_internet
from app.schemas import BlindSpotReport

logger = logging.getLogger(__name__)

async def run_echo_breaker_pipeline(
    url: Optional[str] = None,
    text: Optional[str] = None,
    image_base64: Optional[str] = None,
    title: Optional[str] = None
) -> BlindSpotReport:
    """
    Pattern 3: Multi-Step LangChain Pipeline Orchestration
    
    Step 1: Extract core topic, claims, and stance (Chain 1) + OCR Image Vision if screenshot attached
    Step 2: Retrieve live internet search context for counter-perspectives
    Step 3: Contrast framing & analyze omitted facts/veracity (Chain 2)
    Step 4: Synthesize structured final sidebar report (Chain 3)
    """
    content_payload = ""
    metadata_info = f"URL: {url or 'N/A'} | Title: {title or 'N/A'}"

    # Handle image screenshot extraction via Gemini Vision
    if image_base64 and len(image_base64) > 50:
        logger.info("Pattern 3 Pipeline: Extracting text from screenshot via Gemini Vision...")
        extracted_img_text = await extract_image_content(image_base64)
        if text and len(text.strip()) > 20:
            content_payload = f"{text}\n\nSCREENSHOT OCR CONTENT:\n{extracted_img_text}"
        else:
            content_payload = extracted_img_text
    elif text and len(text.strip()) > 20:
        content_payload = text
    elif url:
        content_payload = f"Article at URL {url}. Title: {title or 'News Article'}."
    else:
        content_payload = "General news article and political narrative analysis."

    logger.info(f"Pattern 3 Pipeline: Starting Chain 1 (Extract & Summarize) on payload length {len(content_payload)}...")
    chain1_output = await run_chain_extractor(content_payload, metadata_info)

    # 2. Retrieve Live Internet Context using generated queries
    queries = chain1_output.get("search_queries", [])
    primary_query = queries[0] if queries else f"{chain1_output.get('core_topic', 'news')} opposing views missing facts"
    
    logger.info(f"Pattern 3 Pipeline: Performing live internet search for: '{primary_query}'...")
    search_results = await search_live_internet(primary_query, max_results=5)

    # 3. Step 2: Analyze Blind Spots (Chain 2)
    logger.info("Pattern 3 Pipeline: Starting Chain 2 (Analyze Blind Spots & Veracity)...")
    chain2_output = await run_chain_blindspot(chain1_output, search_results)

    # 4. Step 3: Synthesize Final Report (Chain 3)
    logger.info("Pattern 3 Pipeline: Starting Chain 3 (Synthesize Final Report)...")
    final_report = await run_chain_synthesizer(chain1_output, chain2_output, search_results)

    return final_report
