from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


ToolName = Literal[
    "get_company_info",
    "mock_web_search",
    "translate_document",
    "generate_document",
    "security_filter",
]


class ToolStep(BaseModel):
    """A single planned tool call."""

    tool: ToolName
    args: Dict[str, Any] = Field(default_factory=dict)


class AgentPlan(BaseModel):
    company_name: str
    target_language: str = "en"
    steps: List[ToolStep]


class RedactionResult(BaseModel):
    redacted_text: str
    matched_terms: List[str] = []


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: Any = None
    error: Optional[str] = None


class TraceEvent(BaseModel):
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(BaseModel):
    instruction: str
    plan: AgentPlan
    trace: List[TraceEvent]
    final_document: str
    redactions: List[str] = Field(default_factory=list)
