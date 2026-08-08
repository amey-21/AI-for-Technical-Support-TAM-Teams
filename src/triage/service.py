import json
import re

from src.common.llm import LLMClient
from src.common.models import TicketInput, TriageResult
from src.common.prompts import TRIAGE_PROMPT_VERSION, TRIAGE_SYSTEM
from src.common.retrieval import retrieve

PRODUCTS = {
    "databridge pro": "DataBridge Pro",
    "cloudsync": "CloudSync",
    "analyticshub": "AnalyticsHub",
    "securevault": "SecureVault",
    "workflowengine": "WorkflowEngine",
}
MODULES = {
    "DataBridge Pro": ("Data Ingestion", "Schema Management", "Pipeline Monitoring", "Connectors", "API"),
    "CloudSync": ("File Sync", "Conflict Resolution", "Permissions", "Bandwidth Limits", "Integrations"),
    "AnalyticsHub": ("Dashboard", "Reports", "Data Sources", "Alerts", "Exports"),
    "SecureVault": ("Authentication", "Encryption", "Audit Logs", "Key Management", "SSO Configuration"),
    "WorkflowEngine": ("Triggers", "Actions", "Scheduling", "Error Handling", "Templates"),
}

def _product_area(text: str, product: str, kb_heading: str | None) -> str:
    """Return a useful Product / Module value instead of a product name alone."""
    lower = text.lower()
    module = next((m for m in MODULES.get(product, ()) if m.lower() in lower), None)
    if not module and kb_heading:
        module = next((m for m in MODULES.get(product, ()) if m.lower() in kb_heading.lower()), None)
    # Cross-product troubleshooting signals map to the most useful module.
    if not module and product == "SecureVault" and any(x in lower for x in ("sso", "saml", "idp")): module = "SSO Configuration"
    if not module and product == "CloudSync" and any(x in lower for x in ("sso", "saml", "oauth", "integration")): module = "Integrations"
    if not module and product == "DataBridge Pro" and any(x in lower for x in ("pipeline", "throughput", "timeout")): module = "Pipeline Monitoring"
    if not module and product == "AnalyticsHub" and any(x in lower for x in ("dashboard", "query", "timeout")): module = "Dashboard"
    return f"{product} / {module}" if module else product

def _local_triage(ticket: TicketInput) -> TriageResult:
    text = f"{ticket.subject}\n{ticket.body}".lower()
    product = next((v for k, v in PRODUCTS.items() if k in text), "General Support")
    if re.search(r"\b(data loss|lost|missing data|deleted|corrupt)\b", text): category = "Data Loss"
    elif re.search(r"\b(invoice|billing|payment|refund|charge|plan|subscription)\b", text): category = "Billing"
    elif re.search(r"\b(onboard|setup|new user|training|provision)\b", text): category = "Onboarding"
    elif re.search(r"\b(salesforce|snowflake|webhook|api|integration|connector|sso|saml|oauth)\b", text): category = "Integration"
    elif re.search(r"\b(slow|timeout|latency|throughput|performance|stalled|rate.limit)\b|err_connection_timeout|pipeline_stalled|rate_limit_exceeded", text): category = "Performance"
    elif re.search(r"\b(request|would like|feature|bulk)\b", text): category = "Feature Request"
    elif re.search(r"\b(how (do|to)|where (do|can)|help (with|me))\b", text): category = "How-To"
    else: category = "Bug"
    if re.search(r"\b(data loss|production down|business (is )?stopped|all users|critical)\b", text): urgency = "P1"
    elif re.search(r"\b(urgent|impacting|unable|failing|outage|\b[1-9][0-9]+ users)\b", text): urgency = "P2"
    elif re.search(r"\b(slow|workaround|request|issue)\b", text): urgency = "P3"
    else: urgency = "P4"
    kb = retrieve(f"{ticket.subject} {ticket.body}")
    matched = f"{kb.path} :: {kb.heading}" if kb else None
    product_area = _product_area(text, product, kb.heading if kb else None)
    team = "Incident Response" if urgency == "P1" else ({"Billing": "Billing Operations", "Onboarding": "Customer Success", "Feature Request": "Product Management", "Integration": "Integrations Support", "Performance": "Platform Support"}.get(category, f"{product} Support"))
    why = f"Classified as {category} for {product_area} based on the reported issue pattern; impact language supports {urgency}."
    reference = f" See {matched}." if matched else ""
    response = f"Thanks for contacting support. We have routed this to {team} as {urgency}.{reference} We will review the details and update you with next steps."
    return TriageResult(product_area=product_area, category=category, urgency=urgency, reasoning=why, matched_kb_doc=matched, recommended_team=team, draft_response=response)

def triage_ticket(ticket: TicketInput | str, llm_client: LLMClient | None = None) -> TriageResult:
    """Triage text or a structured ticket, using LangChain when configured.

    A local policy is the explicit no-secret fallback, and also protects availability
    when a configured provider errors or returns invalid structured content.
    """
    input_ticket = TicketInput(body=ticket) if isinstance(ticket, str) else ticket
    local = _local_triage(input_ticket)
    client = llm_client or LLMClient()
    if not client.enabled:
        return local
    kb = retrieve(f"{input_ticket.subject} {input_ticket.body}")
    evidence = {"matched_path": local.matched_kb_doc, "content": kb.text if kb else "No KB match."}
    user = json.dumps({"prompt_version": TRIAGE_PROMPT_VERSION, "ticket": input_ticket.model_dump(), "retrieved_kb": evidence, "routing_policy": local.recommended_team}, ensure_ascii=False)
    try:
        result = client.structured(TRIAGE_SYSTEM, user, TriageResult)
        # Retain the traceable retrieval citation and deterministic routing policy.
        return result.model_copy(update={"product_area": local.product_area, "matched_kb_doc": local.matched_kb_doc, "recommended_team": local.recommended_team})
    except Exception:
        return local
