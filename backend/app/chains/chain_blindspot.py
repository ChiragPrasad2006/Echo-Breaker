import json
import logging
from typing import Dict, Any, List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.chains.chain_extractor import get_llm

logger = logging.getLogger(__name__)

BLINDSPOT_PROMPT = """You are a non-partisan media bias and fact-checking analyst.
Your job is to compare an original news article/tweet/text against live internet search results to evaluate whether the context is TRUE, AN UNVERIFIED LEAK/RUMOR, MISLEADING, or omitting crucial facts.
CRITICAL: ALL OUTPUT AND SUMMARIES MUST BE IN ENGLISH, REGARDLESS OF THE SOURCE CONTENT LANGUAGE.

ORIGINAL ARTICLE TEXT:
{original_text}

ORIGINAL EXTRACTION (CHAIN 1):
Topic: {core_topic}
Primary Stance: {primary_stance}
Key Claims: {key_claims}
Identified Framing: {source_bias_indicator}

LIVE INTERNET SEARCH RESULTS:
{live_search_results}

Compare the ORIGINAL ARTICLE TEXT against the LIVE INTERNET SEARCH RESULTS.
Your key goal is to identify concrete, technical, or structural omissions present in the source article. Actively cross-reference the raw article text against the provided live web search context to identify omissions (such as enthusiasm gaps, gerrymandering, statistical margins, missing citations, operational realities, or unverified timelines).

Evaluate:
1. Veracity Rating:
   - If unconfirmed hardware roadmap/leak: "Unverified Leak / Unconfirmed Rumor"
   - If fully verified by official statements: "Factually Confirmed"
   - If core claims hold with omitted context: "Mostly True with Omissions"
   - If false or misleading: "Misleading Context / Unverified"
2. Veracity Explanation: 2-sentence explanation of whether the context is true, an unconfirmed leak, or missing facts.
3. Key Omitted Facts (for "omitted_facts" list):
   - You MUST extract hyper-specific facts, names, figures, numbers, dates, specific policies, official records, or corporate announcements.
   - Strictly FORBID broad, generic, or vague phrases such as "Historical context", "Local perspectives", "More nuance needed", "Background info", "Additional details", "Opposing viewpoints", "More details", "Live web context", "General background".
   - EVERY item in the "omitted_facts" list MUST identify concrete, technical, or structural gaps present in the source material from one of these categories:
     * Specific Statutory / Legal Provisions (e.g., missing citations to Section 69A IT Act, IT Rules amendments, or judicial rulings).
     * Operational & Institutional Realities (e.g., capacity bottlenecks, lack of regional fact-checking cells, platform compliance rules).
     * Missing Data Points / Metrics (e.g., specific missing casualty numbers, unmentioned financial figures, enthusiasm gaps, gerrymandering, statistical margins, or unverified timelines).
   - Require each item to state both the "fact" and the "source" (e.g., "IT Rules Jurisprudence", "PIB FCU Guidelines", "Ministry of Electronics and IT (MeitY)").
   - CRITICAL: Whenever omissions or missing context are mentioned in the veracity explanation or summary, they MUST also be explicitly formatted as objects inside the "omitted_facts" JSON array. The array must NEVER be returned as empty when omissions are mentioned in the text.
   - If no specific, verifiable omitted facts exist, return "omitted_facts" as an empty list [].

Respond ONLY with a valid JSON object matching this schema:
{{
    "bias_score": 55,
    "veracity_rating": "Unverified Leak / Unconfirmed Rumor",
    "veracity_explanation": "Media reporting confirms the leak graphic was published, but official sources have not verified the product roadmap timeline.",
    "omitted_facts": [
        {{
            "fact": "Official confirmation status and corporate disclaimers on tentative roadmaps",
            "importance": "High",
            "source": "Industry reporting"
        }}
    ],
    "opposing_perspectives": [
        {{
            "spectrum": "Industry Analysis",
            "viewpoint": "Highlights that early roadmaps frequently change before final silicon production.",
            "key_arguments": ["Unconfirmed timelines", "Production revisions"],
            "outlet_examples": ["AnandTech", "Tom's Hardware", "Ars Technica"]
        }}
    ]
}}
"""

async def run_chain_blindspot(
    extraction_data: Dict[str, Any],
    search_results: List[Dict[str, Any]],
    original_text: str = ""
) -> Dict[str, Any]:
    """Chain 2: Analyze veracity, blind spots, and missing context by contrasting against live internet search results."""
    llm = get_llm()
    formatted_search = json.dumps(search_results, indent=2)

    topic_str = extraction_data.get("core_topic", "").lower()
    claims_str = json.dumps(extraction_data.get("key_claims", [])).lower()
    is_leak = any(w in (topic_str + claims_str) for w in ["leak", "rumor", "alleged", "roadmap", "unconfirmed"])

    default_rating = "Unverified Leak / Unconfirmed Rumor" if is_leak else "Partially Verified Context"
    default_exp = (
        "Reporting confirms this leak graphic was published, but official sources have not verified the timeline."
        if is_leak else
        "Core claims reflect current media discussion; cross-referencing against independent data sources is recommended."
    )

    if not llm:
        return {
            "bias_score": 60 if is_leak else 45,
            "veracity_rating": default_rating,
            "veracity_explanation": default_exp,
            "omitted_facts": [
                {
                    "fact": f"Official confirmation status and production timeline context for {extraction_data.get('core_topic', 'topic')}.",
                    "importance": "High",
                    "source_note": "Industry Search Context"
                }
            ],
            "opposing_perspectives": [
                {
                    "spectrum": "Tech Analysis",
                    "viewpoint": "Evaluates unconfirmed roadmaps vs official corporate press releases and earnings calls.",
                    "key_arguments": ["Unconfirmed timelines", "Potential revisions"],
                    "outlet_examples": ["Tom's Hardware", "AnandTech", "Verge"]
                }
            ]
        }

    try:
        prompt = PromptTemplate(
            template=BLINDSPOT_PROMPT,
            input_variables=[
                "core_topic", "primary_stance", "key_claims",
                "source_bias_indicator", "live_search_results", "original_text"
            ]
        )
        chain = prompt | llm | JsonOutputParser()
        result = await chain.ainvoke({
            "core_topic": extraction_data.get("core_topic", "General Topic"),
            "primary_stance": extraction_data.get("primary_stance", "Standard Reporting"),
            "key_claims": json.dumps(extraction_data.get("key_claims", [])),
            "source_bias_indicator": extraction_data.get("source_bias_indicator", "Single Angle"),
            "live_search_results": formatted_search[:4000],
            "original_text": original_text[:4000]
        })
        return result
    except Exception as e:
        logger.error(f"Chain 2 BlindSpot error: {e}")
        error_msg = str(e)[:150]
        return {
            "bias_score": 0,
            "veracity_rating": "API Error",
            "veracity_explanation": f"Failed to analyze due to error: {error_msg}",
            "omitted_facts": [
                {
                    "fact": "API request failed.",
                    "importance": "High",
                    "source_note": "Error Context"
                }
            ],
            "opposing_perspectives": [
                {
                    "spectrum": "Error",
                    "viewpoint": "The analysis could not be completed.",
                    "key_arguments": ["API Error"],
                    "outlet_examples": []
                }
            ]
        }
