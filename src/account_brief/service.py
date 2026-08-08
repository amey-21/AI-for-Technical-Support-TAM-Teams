import json
from datetime import timedelta

from src.common.data import accounts, account_tickets, dataset_max_date
from src.common.llm import LLMClient
from src.common.models import AccountBrief, RiskItem
from src.common.prompts import ACCOUNT_BRIEF_PROMPT_VERSION, ACCOUNT_BRIEF_SYSTEM

RISK_WORDS = ("churn", "cancel", "compet", "frustrat", "escalat", "unacceptable", "switch")

def _local_account_brief(account_id: str) -> AccountBrief | None:
    account = next((a for a in accounts() if a["account_id"] == account_id), None)
    if not account: return None
    ts = sorted(account_tickets(account_id), key=lambda t: (t["created_at"], t["ticket_id"]), reverse=True)
    risks: list[RiskItem] = []
    for note in account.get("escalation_notes") or []:
        risks.append(RiskItem(risk=note, severity="high" if any(x in note.lower() for x in RISK_WORDS) else "medium", source="account.escalation_notes"))
    for t in ts:
        body = t.get("body", "")
        if t["urgency"] == "P1" or any(x in body.lower() for x in RISK_WORDS):
            quote = next((s.strip() for s in body.split(".") if any(x in s.lower() for x in RISK_WORDS)), body.split("\n")[0].strip())
            risks.append(RiskItem(risk=f"{t['ticket_id']}: {t['subject']}", severity="high" if t["urgency"] == "P1" else "medium", evidence_quote=quote, source=f"ticket:{t['ticket_id']}"))
    risks = risks[:8]
    active = account.get("seats_active") or 0; licensed = account.get("seats_licensed") or 0
    summary = (f"{account['company']} is a {account['plan_tier']} account with ${account['arr_usd']:,} ARR and {account['health_status'].lower()} health. "
        f"Usage is {account['usage_trend'].lower()} ({active}/{licensed} licensed seats active), and {len(ts)} tickets fall in the dataset-relative 90-day window. "
        f"The account has {account.get('open_tickets', 0)} open tickets and {account.get('p1_tickets_last_30d', 0)} P1 tickets in the last 30 days. "
        f"NPS is {account['nps_score'] if account.get('nps_score') is not None else 'not available'}.")
    talking = ["Confirm progress and ownership for open support items.", f"Review adoption for {', '.join(account.get('products') or ['the deployed products'])} and agree on an improvement plan."]
    if risks: talking.insert(0, "Address the escalated risk signals and agree on dated follow-up actions.")
    if account["usage_trend"] in ("Declining", "Inactive"): talking.append("Discuss barriers to active-seat adoption and schedule targeted enablement.")
    end = dataset_max_date(); start = end - timedelta(days=90)
    return AccountBrief(account_id=account_id, company=account["company"], executive_summary=summary, open_risks_and_flagged_issues=risks, recommended_talking_points=talking, ticket_window_start=start.date().isoformat(), ticket_window_end=end.date().isoformat(), tickets_considered=len(ts))

def _normalise_llm_brief(candidate: AccountBrief, baseline: AccountBrief) -> AccountBrief:
    """Restore canonical identity/window fields, ordering, and quote-safe risks.

    The configured model receives temperature 0 and a fixed seed. This additional
    normalization ensures source citations and ordering remain deterministic even if
    a provider formats a structured response differently.
    """
    by_source = {risk.source: risk for risk in candidate.open_risks_and_flagged_issues}
    normalised_risks: list[RiskItem] = []
    for baseline_risk in baseline.open_risks_and_flagged_issues:
        proposed = by_source.get(baseline_risk.source)
        if baseline_risk.source.startswith("ticket:"):
            # Preserve direct, known-verbatim evidence rather than trusting paraphrases.
            normalised_risks.append(baseline_risk if not proposed or proposed.evidence_quote != baseline_risk.evidence_quote else proposed)
        elif proposed:
            normalised_risks.append(proposed)
        else:
            normalised_risks.append(baseline_risk)
    talking = list(dict.fromkeys(point.strip() for point in candidate.recommended_talking_points if point.strip()))[:5]
    if not talking: talking = baseline.recommended_talking_points
    summary = candidate.executive_summary.strip()
    if not summary or len(summary.split(". ")) < 3: summary = baseline.executive_summary
    return AccountBrief(account_id=baseline.account_id, company=baseline.company, executive_summary=summary, open_risks_and_flagged_issues=normalised_risks, recommended_talking_points=talking, ticket_window_start=baseline.ticket_window_start, ticket_window_end=baseline.ticket_window_end, tickets_considered=baseline.tickets_considered)

def get_account_brief(account_id: str, llm_client: LLMClient | None = None) -> AccountBrief | None:
    baseline = _local_account_brief(account_id)
    if baseline is None: return None
    client = llm_client or LLMClient()
    if not client.enabled:
        return baseline
    account = next(a for a in accounts() if a["account_id"] == account_id)
    recent = sorted(account_tickets(account_id), key=lambda ticket: (ticket["created_at"], ticket["ticket_id"]), reverse=True)
    user = json.dumps({"prompt_version": ACCOUNT_BRIEF_PROMPT_VERSION, "account": account, "recent_tickets": recent, "canonical_risk_evidence": [risk.model_dump() for risk in baseline.open_risks_and_flagged_issues], "output_window": {"start": baseline.ticket_window_start, "end": baseline.ticket_window_end}}, ensure_ascii=False)
    try:
        candidate = client.structured(ACCOUNT_BRIEF_SYSTEM, user, AccountBrief)
        return _normalise_llm_brief(candidate, baseline)
    except Exception:
        return baseline
