# AI Support & TAM Tooling

Production-adjacent FastAPI tooling for support-ticket triage and TAM account-health briefs. It uses **only** the supplied JSON and Markdown corpus. The default local policy is deterministic and needs no credentials. When configured, LangChain invokes an OpenAI or OpenAI-compatible model through a single Pydantic structured-output boundary.

## Setup

Requires Python 3.11+.

```powershell
python -m venv .venv
. .\activate-venv.ps1
pip install -r requirements.txt
Copy-Item .env.example .env  # optional; leave values blank for local mode
```

Never commit credentials. For optional LLM mode, configure only local/deployment secrets:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=...
LLM_BASE_URL=
LLM_SEED=42
```

`LLM_PROVIDER` can be `openai` or `openai_compatible`; the latter uses `LLM_BASE_URL` for a compatible endpoint. The LangChain client uses `temperature=0`, a fixed seed, and tool/function structured output into Pydantic models. If it is unconfigured or errors, the services safely use their deterministic local policy.

## Run Tasks 1 and 2

```powershell
uvicorn src.main:app --reload
```

Use `http://127.0.0.1:8000/docs`, or these sample calls:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/triage -ContentType 'application/json' -Body '{"subject":"Pipeline timeout","body":"DataBridge Pro returns ERR_CONNECTION_TIMEOUT after 30s and is impacting users."}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/triage/text -ContentType 'text/plain' -Body 'CloudSync SSO reports GROUP_NOT_MAPPED for new users.'
Invoke-RestMethod http://127.0.0.1:8000/account-brief/ACC-3336
```

Callable APIs are `src.triage.triage_ticket(TicketInput(...))` (or `triage_ticket("raw text")`) and `src.account_brief.get_account_brief(account_id)`. Unknown IDs return a clear 404 from the API and `None` from the callable function.

## Triage routing, RAG, and LLM flow

The deterministic policy applies this category precedence: Data Loss, Billing, Onboarding, Integration, Performance, Feature Request, How-To, then Bug. P1 is reserved for explicit critical/data-loss/business-stopped signals; P2 captures urgent, failed, or materially impacted reports; P3 covers a workaround/request/moderate issue; P4 is low impact. P1 goes to Incident Response; Billing to Billing Operations; Onboarding to Customer Success; Feature Requests to Product Management; Integration and Performance have specialist support; other tickets go to product support.

`product_area` is inferred as `Product / Module` whenever possible, for example `DataBridge Pro / Pipeline Monitoring`, using explicit module mentions and KB headings. Markdown is split on `---`; heading metadata is preserved; deterministic lexical scoring retrieves a relevant path/section. Explicit error codes prefer the troubleshooting error-reference tables.

In LLM mode, the LangChain triage prompt receives the ticket, the selected KB chunk, and deterministic routing context, and returns `TriageResult` via structured Pydantic tool output. The account-brief prompt receives only the account, its recent tickets, and canonical risk evidence. The brief normalizer restores canonical identity/window fields, risk ordering, and known-verbatim ticket quotes after the zero-temperature, fixed-seed model response. This maintains deterministic evidence behavior even when provider formatting differs.

Prompts are versioned in [`src/common/prompts.py`](src/common/prompts.py), including a changelog, so evaluation changes can be traced to prompt revisions.

## Evaluation (Task 3)

Run the standalone harness (this regenerates the committed report):

```powershell
python -m src.evals.run
```

It contains 10 acceptance cases: five triage cases (including an ambiguous request) and five account-brief cases (including null NPS and zero recent tickets). Rule checks validate enums/schema, KB routing, quote provenance, unknown-account behavior, and deterministic data conditions. When LLM credentials are configured, a LangChain Pydantic `JudgeResult` assesses groundedness, specificity, and coherence. The committed no-secret report explicitly records its deterministic heuristic fallback, so it remains reproducible in CI.

By default the harness deliberately forces deterministic local mode, even when a developer has an LLM-configured `.env`. To exercise the optional provider and judge path manually, run:

```powershell
$env:EVAL_WITH_LLM = '1'
python -m src.evals.run
Remove-Item Env:EVAL_WITH_LLM
```

Optional unit checks:

```powershell
python -m unittest discover -s tests -v
```

See [DESIGN_NOTE.md](DESIGN_NOTE.md) for production failure modes, latency/quality, data sensitivity, and scaling.

## Bonus: Streamlit workspace

The non-technical interface provides a ticket form and account selector, readable risk cards with direct source quotes, and TAM talking points. It calls the same Python services as the API, so the UI and API behavior stay consistent.

```powershell
streamlit run ui/app.py
```

Streamlit will show the local URL (normally `http://localhost:8501`).

## Bonus: streamed TAM brief

The API can send a completed account brief section by section using Server-Sent Events (SSE):

```text
GET /account-brief/{account_id}/stream
```

For example, while the FastAPI server is running:

```powershell
curl.exe -N http://127.0.0.1:8000/account-brief/ACC-3336/stream
```

The deterministic stream emits `metadata`, `executive_summary`, `open_risks`, `talking_points`, and `complete` events. This gives the UI/client immediate useful sections without waiting for a single combined payload.
