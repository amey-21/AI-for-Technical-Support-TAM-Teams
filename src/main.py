import json
from collections.abc import Iterator

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from src.common.data import accounts
from src.common.models import TicketInput, TriageResult, AccountBrief
from src.triage import triage_ticket
from src.account_brief import get_account_brief
app = FastAPI(title="AI Support and TAM Tooling")

def _sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

def _brief_events(brief: AccountBrief) -> Iterator[str]:
    """Deterministically stream the three TAM-brief sections as SSE events."""
    yield _sse("metadata", {"account_id": brief.account_id, "company": brief.company, "tickets_considered": brief.tickets_considered, "ticket_window_start": brief.ticket_window_start, "ticket_window_end": brief.ticket_window_end})
    yield _sse("executive_summary", {"title": "Executive summary", "content": brief.executive_summary})
    yield _sse("open_risks", {"title": "Open risks & flagged issues", "content": [risk.model_dump() for risk in brief.open_risks_and_flagged_issues]})
    yield _sse("talking_points", {"title": "Recommended talking points for the TAM", "content": brief.recommended_talking_points})
    yield _sse("complete", {"account_id": brief.account_id})

def _account_brief_stream(account_id: str) -> Iterator[str]:
    """Send an immediate SSE event, then stream each completed brief section."""
    yield _sse("status", {"message": "Generating account brief", "account_id": account_id})
    brief = get_account_brief(account_id)
    # The endpoint performs the existence check before constructing this generator.
    if brief is not None:
        yield from _brief_events(brief)

    
@app.post("/triage", response_model=TriageResult)
def triage(ticket: TicketInput):
    """Triage a JSON ticket with optional subject and required body."""
    return triage_ticket(ticket)

@app.post("/triage/text", response_model=TriageResult)
def triage_text(ticket_body: str = Body(..., media_type="text/plain", min_length=1)):
    """Triage a raw text/plain ticket."""
    return triage_ticket(ticket_body)


@app.get("/account-brief/{account_id}", response_model=AccountBrief)
def account_brief(account_id: str):
    result = get_account_brief(account_id)
    if result is None: raise HTTPException(status_code=404, detail=f"Account '{account_id}' was not found in accounts.json.")
    return result

@app.get("/account-brief/{account_id}/stream", response_class=StreamingResponse)
def stream_account_brief(account_id: str):
    """Stream a TAM brief using Server-Sent Events without artificial delay."""
    if not any(account["account_id"] == account_id for account in accounts()):
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' was not found in accounts.json.")
    return StreamingResponse(_account_brief_stream(account_id), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
