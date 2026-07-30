import logging
import asyncio
from typing import Dict, Any, Optional
from app.chains.chain_extractor import run_chain_extractor, extract_image_content
from app.chains.chain_blindspot import run_chain_blindspot
from app.chains.chain_synthesizer import run_chain_synthesizer
from app.services.web_search import search_live_internet
from app.schemas import BlindSpotReport

logger = logging.getLogger(__name__)

async def retry_with_backoff(coro_func, *args, max_retries: int = 3, initial_delay: float = 1.0, **kwargs):
    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            is_429 = "429" in err_str or "rate limit" in err_str.lower()
            if is_429 and attempt < max_retries:
                logger.warning(
                    f"429 Rate Limit encountered. Retrying in {delay}s (Attempt {attempt + 1}/{max_retries}). "
                    f"Error: {err_str[:100]}"
                )
                await asyncio.sleep(delay)
                delay *= 2.0  # Exponential backoff
            else:
                raise e

def get_pipeline_fallback_report(error_desc: str) -> BlindSpotReport:
    from app.schemas import OmittedFact
    return BlindSpotReport(
        core_topic="Pipeline Error Occurred",
        core_summary=f"Analysis failed during pipeline execution. Details: {error_desc}",
        detected_framing="Error State",
        bias_score=0,
        veracity_rating="Pipeline Execution Error",
        veracity_explanation="The backend pipeline encountered an unexpected error while executing analysis chains.",
        primary_stance="Error Stance",
        key_omitted_facts=[
            OmittedFact(
                fact="Pipeline execution failed to complete all extraction steps.",
                importance="High",
                source="Error Logs"
            )
        ],
        opposing_perspectives=[],
        internet_citations=[],
        neutral_synthesis="No synthesis is available due to a processing error.",
        suggested_questions=[]
    )

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

    # 1. Step 1: Extract core topic, claims, and stance (Chain 1)
    try:
        logger.info(f"Pattern 3 Pipeline: Starting Chain 1 (Extract & Summarize) on payload length {len(content_payload)}...")
        chain1_output = await retry_with_backoff(run_chain_extractor, content_payload, metadata_info)
    except Exception as e:
        missing_key = e.args[0] if isinstance(e, KeyError) else "N/A"
        logger.error(f"Chain 1 execution failed. Missing key: {missing_key}. Error details: {str(e)}")
        return get_pipeline_fallback_report(f"Chain 1 (Extractor) execution failed due to missing key: {missing_key}")

    # 2. Retrieve Live Internet Context using generated queries
    try:
        queries = chain1_output.get("search_queries", [])
        primary_query = queries[0] if queries else f"{chain1_output.get('core_topic', 'news')} opposing views missing facts"
        logger.info(f"Pattern 3 Pipeline: Performing live internet search for: '{primary_query}'...")
        search_results = await search_live_internet(primary_query, max_results=5)
    except Exception as e:
        missing_key = e.args[0] if isinstance(e, KeyError) else "N/A"
        logger.error(f"Web search step failed. Missing key: {missing_key}. Error details: {str(e)}")
        return get_pipeline_fallback_report(f"Search retrieval step failed due to missing key: {missing_key}")

    # 3. Step 2: Analyze Blind Spots (Chain 2)
    try:
        logger.info("Pattern 3 Pipeline: Starting Chain 2 (Analyze Blind Spots & Veracity)...")
        chain2_output = await retry_with_backoff(run_chain_blindspot, chain1_output, search_results, content_payload)
    except Exception as e:
        missing_key = e.args[0] if isinstance(e, KeyError) else "N/A"
        logger.error(f"Chain 2 execution failed. Missing key: {missing_key}. Error details: {str(e)}")
        return get_pipeline_fallback_report(f"Chain 2 (Blindspot) execution failed due to missing key: {missing_key}")

    # 4. Step 3: Synthesize Final Report (Chain 3)
    try:
        logger.info("Pattern 3 Pipeline: Starting Chain 3 (Synthesize Final Report)...")
        final_report = await retry_with_backoff(run_chain_synthesizer, chain1_output, chain2_output, search_results)
    except Exception as e:
        missing_key = e.args[0] if isinstance(e, KeyError) else "N/A"
        logger.error(f"Chain 3 execution failed. Missing key: {missing_key}. Error details: {str(e)}")
        return get_pipeline_fallback_report(f"Chain 3 (Synthesizer) execution failed due to missing key: {missing_key}")

    # Safety fallback: If synthesizer returns empty/fallback list but blindspot has valid omissions
    fallback_text = "No critical statutory, legal, or factual omissions detected in the primary claims."
    is_empty_or_fallback = (
        not final_report.key_omitted_facts or
        (len(final_report.key_omitted_facts) == 1 and final_report.key_omitted_facts[0].fact == fallback_text)
    )
    if is_empty_or_fallback:
        blindspot_omitted = chain2_output.get("omitted_facts", [])
        if isinstance(blindspot_omitted, list) and len(blindspot_omitted) > 0:
            valid_blindspot_omitted = []
            for item in blindspot_omitted:
                if isinstance(item, dict) and item.get("fact"):
                    fact_val = item.get("fact", "").strip()
                    # Filter out generic phrases
                    is_generic = False
                    fact_lower = fact_val.lower()
                    generic_phrases = ["historical context", "local perspectives", "more nuance needed", "background info", "additional details", "opposing viewpoints", "more details", "live web context", "general background"]
                    for gp in generic_phrases:
                        if gp in fact_lower:
                            is_generic = True
                            break
                    if fact_val and not is_generic and fact_val != fallback_text:
                        source_val = item.get("source") or item.get("verifying_source") or item.get("source_note") or "Verification Engine"
                        from app.schemas import OmittedFact
                        valid_blindspot_omitted.append(
                            OmittedFact(
                                fact=fact_val,
                                importance=item.get("importance", "High"),
                                source=source_val
                            )
                        )
            if valid_blindspot_omitted:
                logger.info(f"Pipeline Safety Fallback triggered: carrying over {len(valid_blindspot_omitted)} omissions from Chain 2.")
                final_report.key_omitted_facts = valid_blindspot_omitted

    # Fallback 2: If key_omitted_facts still has fallback values but core_summary has omissions phrases
    fallback_texts = [
        "No critical statutory, legal, or factual omissions detected in the primary claims.",
        "No critical omitted facts identified"
    ]
    is_still_fallback = (
        not final_report.key_omitted_facts or
        (len(final_report.key_omitted_facts) == 1 and any(fb in final_report.key_omitted_facts[0].fact for fb in fallback_texts))
    )
    if is_still_fallback and final_report.core_summary:
        import re
        sentences = re.split(r'(?<=[.!?])\s+', final_report.core_summary)
        keywords = ["lacks context", "backed off", "omits", "omission", "omitted", "backed-off", "lack of authority"]
        extracted_facts = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(kw in sentence_lower for kw in keywords):
                from app.schemas import OmittedFact
                clean_fact = sentence.strip()
                if clean_fact.endswith('.'):
                    clean_fact = clean_fact[:-1]
                extracted_facts.append(
                    OmittedFact(
                        fact=clean_fact,
                        importance="High",
                        source="Core Summary Analysis"
                    )
                )
        if extracted_facts:
            logger.info(f"Pipeline Fallback 2: Extracted {len(extracted_facts)} omissions from core summary.")
            final_report.key_omitted_facts = extracted_facts

    return final_report
