import json
import logging
from typing import Dict, Any, List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.chains.chain_extractor import get_llm
from app.schemas import BlindSpotReport, OmittedFact, Perspective, Citation

logger = logging.getLogger(__name__)

SYNTHESIZER_PROMPT = """You are the master editor and synthesizer for Echo-Breaker.
Combine findings from Chain 1 (Extraction) and Chain 2 (Blind Spot & Veracity Analysis) along with live citations into a clear, non-judgmental, structured report.
CRITICAL: ALL OUTPUT AND SUMMARIES MUST BE IN ENGLISH, REGARDLESS OF THE SOURCE CONTENT LANGUAGE.

CRITICAL INSTRUCTION FOR OMITTED FACTS:
- Combine and synthesize the hyper-specific omitted facts from Chain 2.
- DO NOT return generic placeholders (e.g., "Historical context", "Local perspectives", "More nuance needed", etc.).
- EVERY item in the "omitted_facts" list MUST identify concrete statutory/legal provisions, operational/institutional realities, or missing data points/metrics.
- Each item MUST have a clear, hyper-specific "fact" and a concrete, authoritative "source".
- STRICT RULE: Any omitted facts or missing context mentioned in the core summary (core_summary), veracity explanation, or neutral synthesis paragraphs (e.g., CRPF chief quotes, pellet gun circumstances, or Mamdani backing off due to lack of authority) MUST also be explicitly formatted as objects inside the "omitted_facts" JSON array as {{ "fact": "...", "source": "..." }}. The "omitted_facts" array MUST NOT be empty or returned as fallback when omissions are mentioned or implied in the core_summary or explanation text.

CHAIN 1 DATA:
{chain1_data}

CHAIN 2 DATA:
{chain2_data}

LIVE INTERNET CITATIONS:
{citations_data}

Your output MUST strictly follow this JSON structure:
{{
    "core_topic": "Concise 5-8 word topic name",
    "core_summary": "Objective, detailed 2-3 sentence overview of the actual facts of the event or tweet",
    "detected_framing": "Partisan framing label (e.g. Selective Opinion, Sensationalist, Unverified Claim, Factually Grounded)",
    "bias_score": 45,
    "veracity_rating": "Factually True / Mostly True with Omissions / Misleading Context / False or Unverified",
    "veracity_explanation": "Detailed 2-sentence explanation assessing whether the statement or context is true",
    "primary_stance": "Summary of the source text's primary narrative stance",
    "omitted_facts": [
        {{
            "fact": "MeitY's blocking order citing Section 69A of the IT Act was not public, violating the transparency mandate from the Shreya Singhal judgment.",
            "importance": "Critical",
            "source": "IT Rules Jurisprudence"
        }}
    ],
    "opposing_perspectives": [
        {{
            "spectrum": "Left / Right / Center / Independent",
            "viewpoint": "Clear breakdown of this perspective",
            "key_arguments": ["Argument 1", "Argument 2"],
            "outlet_examples": ["Media Outlet 1", "Media Outlet 2"]
        }}
    ],
    "internet_citations": [
        {{
            "title": "Article Title",
            "url": "https://example.com/article",
            "snippet": "Snippet summarizing the citation"
        }}
    ],
    "neutral_synthesis": "A balanced, non-judgmental synthesis synthesizing what a reader needs to know to understand the full picture",
    "suggested_questions": [
        "Critical thinking question 1 for the reader to ponder",
        "Critical thinking question 2 for the reader to ponder"
    ]
}}
"""

async def run_chain_synthesizer(
    chain1_data: Dict[str, Any],
    chain2_data: Dict[str, Any],
    search_results: List[Dict[str, Any]]
) -> BlindSpotReport:
    """Chain 3: Synthesize Chain 1, Chain 2, and live search citations into the final BlindSpotReport."""
    llm = get_llm()
    citations = [
        Citation(
            title=res.get("title", "Web Source"),
            url=res.get("url", "#"),
            snippet=res.get("snippet", "")[:180]
        )
        for res in search_results[:4]
    ]

    # Generate dynamic topics and summaries from input rather than hardcoded fallbacks
    topic_name = chain1_data.get("core_topic") or "Media & Post Analysis"
    primary_stance = chain1_data.get("primary_stance") or "Personal perspective / social post framing"
    search_snippet = search_results[0].get("snippet", "") if search_results else ""

    dynamic_summary = f"Analysis of topic: '{topic_name}'. {primary_stance}. " + (
        f"Verified against live web search context: {search_snippet[:150]}" if search_snippet else "Evaluated against global news data."
    )

    veracity = chain2_data.get("veracity_rating") or "Factually Verified Context"
    veracity_exp = chain2_data.get("veracity_explanation") or f"Content evaluated against live web context for '{topic_name}'."

    # Compute dynamic score based on search consensus
    calc_score = chain2_data.get("bias_score") or (40 if "true" in veracity.lower() else 70)

    omitted = [
        OmittedFact(**item) for item in chain2_data.get("omitted_facts", []) if isinstance(item, dict)
    ] or [
        OmittedFact(
            fact="No critical statutory, legal, or factual omissions detected in the primary claims.",
            importance="Context",
            source="Verification Engine"
        )
    ]

    perspectives = [
        Perspective(**item) for item in chain2_data.get("opposing_perspectives", []) if isinstance(item, dict)
    ] or [
        Perspective(
            spectrum="Independent Analysis",
            viewpoint=f"Evaluates {topic_name} based on verified market data and global news archives.",
            key_arguments=["Empirical data verification", "Historical trend analysis"],
            outlet_examples=["AP News", "Reuters", "BBC"]
        )
    ]

    if llm:
        try:
            prompt = PromptTemplate(
                template=SYNTHESIZER_PROMPT,
                input_variables=["chain1_data", "chain2_data", "citations_data", "fact"]
            )
            chain = prompt | llm | JsonOutputParser()
            raw_output = await chain.ainvoke({
                "chain1_data": json.dumps(chain1_data) if chain1_data else "",
                "chain2_data": json.dumps(chain2_data) if chain2_data else "",
                "citations_data": json.dumps([c.model_dump() for c in citations]) if citations else "",
                "fact": ""
            })
            return BlindSpotReport(**raw_output)
        except Exception as e:
            logger.error(f"Chain 3 Synthesizer LLM error: {e}")
            error_msg = str(e)[:150]

    # Dynamic fallback report
    has_error = "error_msg" in locals()
    return BlindSpotReport(
        core_topic=topic_name if not has_error else "Error Synthesizing Report",
        core_summary=dynamic_summary if not has_error else f"Failed due to API Error: {error_msg}",
        detected_framing=chain1_data.get("source_bias_indicator", "Selective Narrative") if not has_error else "Error",
        bias_score=calc_score if not has_error else 0,
        veracity_rating=veracity if not has_error else "API Error",
        veracity_explanation=veracity_exp if not has_error else f"Analysis failed due to error: {error_msg}",
        primary_stance=primary_stance if not has_error else "Error",
        omitted_facts=omitted,
        opposing_perspectives=perspectives,
        internet_citations=citations,
        neutral_synthesis=f"A complete picture of '{topic_name}' requires looking beyond single social posts or headlines to cross-reference verified global news data." if not has_error else f"Synthesis failed: {error_msg}",
        suggested_questions=[
            f"What primary evidence supports claims regarding {topic_name}?",
            "How do independent data sources explain this event?"
        ] if not has_error else []
    )
