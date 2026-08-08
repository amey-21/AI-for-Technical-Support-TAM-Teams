from typing import Literal
from pydantic import BaseModel, Field

Category = Literal["Bug", "Feature Request", "How-To", "Performance", "Billing", "Integration", "Onboarding", "Data Loss"]
Urgency = Literal["P1", "P2", "P3", "P4"]

class TicketInput(BaseModel):
    subject: str = ""
    body: str = Field(min_length=1)

class TriageResult(BaseModel):
    product_area: str
    category: Category
    urgency: Urgency
    reasoning: str
    matched_kb_doc: str | None = None
    recommended_team: str
    draft_response: str

class RiskItem(BaseModel):
    risk: str
    severity: Literal["high", "medium", "low"]
    evidence_quote: str | None = None
    source: str

class AccountBrief(BaseModel):
    account_id: str
    company: str
    executive_summary: str
    open_risks_and_flagged_issues: list[RiskItem]
    recommended_talking_points: list[str]
    ticket_window_start: str
    ticket_window_end: str
    tickets_considered: int

class JudgeResult(BaseModel):
    """Structured quality assessment used by the optional LLM-as-judge path."""
    passed: bool
    quality_score: float = Field(ge=0.0, le=1.0)
    rationale: str
