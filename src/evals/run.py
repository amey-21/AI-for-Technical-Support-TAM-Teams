"""Deterministic acceptance harness; run with `python -m src.evals.run`."""
import json
from pathlib import Path
from src.common.data import ROOT, accounts, account_tickets
from src.common.llm import LLMClient
from src.common.models import TicketInput
from src.triage import triage_ticket
from src.account_brief import get_account_brief
from src.evals.judge import assess_quality

def check(name, task, passed, response, criteria, client):
    if response is None:
        return {"name": name, "task": task, "passed": bool(passed), "quality_score": 1.0 if passed else 0.0, "criteria": criteria, "quality_judge": "not_applicable", "judge_rationale": "Expected empty-state behavior was returned."}
    judge, mode = assess_quality(task, response, criteria, client=client)
    return {"name": name, "task": task, "passed": bool(passed and judge.passed), "quality_score": judge.quality_score if passed and judge.passed else 0.0, "criteria": criteria, "quality_judge": mode, "judge_rationale": judge.rationale}

def run() -> dict:
    # Always prefer the configured LLM. The service and judge implementations
    # independently fall back to deterministic local behavior on no credentials,
    # provider outages, unsupported structured output, or malformed responses.
    client = LLMClient()
    results=[]
    triage_cases = [
      ("authentication error routing", TicketInput(subject="CloudSync SSO fails with GROUP_NOT_MAPPED", body="New users cannot login. GROUP_NOT_MAPPED appears."), lambda r: r.category == "Integration" and r.matched_kb_doc and "authentication-sso" in r.matched_kb_doc),
      ("performance error retrieval", TicketInput(subject="Pipeline timeout", body="DataBridge Pro returns ERR_CONNECTION_TIMEOUT after 30s and is slow."), lambda r: r.category == "Performance" and r.urgency == "P3" and r.matched_kb_doc and "performance-and-integrations" in r.matched_kb_doc),
      ("billing classification", TicketInput(subject="Invoice charge", body="Please explain the unexpected billing charge on our invoice."), lambda r: r.category == "Billing" and r.recommended_team == "Billing Operations"),
      ("data loss priority", TicketInput(subject="Production data missing", body="Critical data loss: all users cannot access deleted production records."), lambda r: r.category == "Data Loss" and r.urgency == "P1"),
      ("adversarial ambiguous request", TicketInput(subject="Need faster bulk export", body="Could you add bulk export? Current workflow is slow but we have a workaround."), lambda r: r.category in {"Feature Request", "Performance"} and r.urgency in {"P2", "P3"} and bool(r.reasoning)),
    ]
    for name, ticket, accept in triage_cases:
        r=triage_ticket(ticket, llm_client=client); results.append(check(name, "triage", accept(r), r, "Output validates through Pydantic and satisfies case-specific routing criteria.", client))
    accts=accounts()
    at_risk=next(a for a in accts if a["health_status"] in ("At Risk", "Churning"))
    null_nps=next(a for a in accts if a.get("nps_score") is None)
    zero=next(a for a in accts if not account_tickets(a["account_id"]))
    account_cases=[
      ("unknown account empty state", "ACC-DOES-NOT-EXIST", lambda r: r is None),
      ("at-risk account summary", at_risk["account_id"], lambda r: r is not None and r.company == at_risk["company"] and len(r.executive_summary.split(". ")) >= 3),
      ("risk quotes are verbatim", at_risk["account_id"], lambda r: all(x.evidence_quote is None or any(x.evidence_quote in t["body"] for t in account_tickets(at_risk["account_id"])) for x in r.open_risks_and_flagged_issues)),
      ("null NPS adversarial case", null_nps["account_id"], lambda r: r is not None and "not available" in r.executive_summary),
      ("zero recent tickets adversarial case", zero["account_id"], lambda r: r is not None and r.tickets_considered == 0),
    ]
    for name, account_id, accept in account_cases:
        r=get_account_brief(account_id, llm_client=client); results.append(check(name, "account brief", accept(r), r, "Valid schema/empty-state and explicit deterministic acceptance condition.", client))
    return {"total_cases":len(results), "passed_cases":sum(x["passed"] for x in results), "aggregate_quality_score":round(sum(x["quality_score"] for x in results)/len(results), 2), "cases":results}

if __name__ == "__main__":
    report=run(); out=ROOT / "eval_report.json"; out.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8"); print(json.dumps(report, indent=2)); raise SystemExit(0 if report["passed_cases"] == report["total_cases"] else 1)
