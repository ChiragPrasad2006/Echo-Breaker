from pydantic import BaseModel, Field, model_validator, field_validator, AliasChoices
from typing import Optional, List, Any

class AnalyzeRequest(BaseModel):
    url: Optional[str] = Field(default=None, description="URL of article to analyze")
    text: Optional[str] = Field(default=None, description="User-selected text or scraped article text")
    image_base64: Optional[str] = Field(default=None, description="Base64 encoded screenshot image")
    title: Optional[str] = Field(default=None, description="Title or headline of the page if available")

class ScrapeRequest(BaseModel):
    url: str = Field(..., description="Target web page URL to scrape")

class ScrapeResponse(BaseModel):
    url: str
    title: str
    text: str
    domain: str

class OmittedFact(BaseModel):
    fact: str = Field(..., description="Crucial fact or context omitted in the source narrative")
    importance: str = Field(default="High", description="Importance level: High, Critical, or Context")
    source: str = Field(
        default="System verification",
        description="Verifying source of the omitted fact",
        validation_alias=AliasChoices("source", "verifying_source", "source_note")
    )

class Perspective(BaseModel):
    spectrum: str = Field(..., description="Political or analytical spectrum: Left, Center, Right, Independent, Global")
    viewpoint: str = Field(..., description="Summary of how this perspective frames the event")
    key_arguments: List[str] = Field(default_factory=list, description="Primary arguments raised by this angle")
    outlet_examples: List[str] = Field(default_factory=list, description="Media outlets typically representing this view")

class Citation(BaseModel):
    title: str
    url: str
    snippet: str

class BlindSpotReport(BaseModel):
    core_topic: str = Field(..., description="The main subject or news event being analyzed")
    core_summary: str = Field(..., description="Objective 2-3 sentence overview of the actual event")
    detected_framing: str = Field(..., description="Identified angle/framing of the source input")
    bias_score: int = Field(..., description="0-100 score indicating blind spot / narrative framing risk")
    veracity_rating: str = Field(default="Mostly True with Omissions", description="Truth rating: Factually True, Mostly True, Misleading Context, False/Unverified")
    veracity_explanation: str = Field(default="Core facts are verified, but key context is omitted.", description="Detailed explanation of whether the context is true")
    primary_stance: str = Field(..., description="Summary of the source material's explicit or implicit stance")
    key_omitted_facts: List[OmittedFact] = Field(default_factory=list, description="Facts, figures, or context omitted in source")
    opposing_perspectives: List[Perspective] = Field(default_factory=list, description="Alternative and opposing perspectives")
    internet_citations: List[Citation] = Field(default_factory=list, description="Live web search citations used for verification")
    neutral_synthesis: str = Field(..., description="A balanced synthesis combining all perspectives")
    suggested_questions: List[str] = Field(default_factory=list, description="Questions the reader should consider to think critically")

    @model_validator(mode="before")
    @classmethod
    def map_omitted_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "omitted_facts" in data and "key_omitted_facts" not in data:
                data["key_omitted_facts"] = data["omitted_facts"]
            if "key_omitted_facts" not in data or data["key_omitted_facts"] is None:
                data["key_omitted_facts"] = []
        return data

    @field_validator("key_omitted_facts", mode="before")
    @classmethod
    def validate_key_omitted_facts(cls, v: Any) -> Any:
        fallback_fact = OmittedFact(
            fact="No critical statutory, legal, or factual omissions detected in the primary claims.",
            importance="Context",
            source="Verification Engine"
        )

        if v is None:
            return [fallback_fact]

        if not isinstance(v, list):
            v = [v]
        
        cleaned = []
        for item in v:
            fact_str = ""
            importance_str = "Context"
            source_str = "Verification Engine"
            
            if isinstance(item, dict):
                fact_str = item.get("fact", "")
                importance_str = item.get("importance", "Context")
                source_str = item.get("source") or item.get("verifying_source") or item.get("source_note") or "Verification Engine"
            elif isinstance(item, OmittedFact):
                fact_str = item.fact
                importance_str = item.importance
                source_str = item.source
            elif isinstance(item, str):
                fact_str = item
                
            fact_str = fact_str.strip() if fact_str else ""
            
            # Forbid broad generic phrases
            is_generic = False
            fact_lower = fact_str.lower()
            generic_phrases = ["historical context", "local perspectives", "more nuance needed", "background info", "additional details", "opposing viewpoints", "more details", "live web context", "general background"]
            for gp in generic_phrases:
                if gp in fact_lower:
                    is_generic = True
                    break
                    
            if fact_str and not is_generic:
                cleaned.append(
                    OmittedFact(
                        fact=fact_str,
                        importance=importance_str if importance_str else "Context",
                        source=source_str if source_str else "Verification Engine"
                    )
                )
                
        if not cleaned:
            return [fallback_fact]
        return cleaned

class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str

class ChatRequest(BaseModel):
    question: str = Field(..., description="User follow-up question")
    selected_text: Optional[str] = Field(default=None, description="Currently selected text on the page")
    context_url: Optional[str] = Field(default=None, description="Active article URL")
    image_base64: Optional[str] = Field(default=None, description="Optional attached image or screenshot")
    report_summary: Optional[str] = Field(default=None, description="Previous blind spot report context")
    history: List[ChatMessage] = Field(default_factory=list, description="Prior conversation turns")

class ChatResponse(BaseModel):
    answer: str
    veracity_check: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
