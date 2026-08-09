# AI Support & TAM Toolkit

Production-adjacent internal tooling for **Technical Support** and **Technical Account Managers (TAMs)**. The repository uses only the supplied synthetic ticket, account, and Markdown knowledge-base data.

| Deliverable | Implementation | Status |
|---|---|---|
| Task 1 | Ticket triage with retrieval, structured output, and FastAPI | ✅ |
| Task 2 | Deterministic TAM account-health brief with quote-backed risks | ✅ |
| Task 3 | Evaluation harness with rules and optional LLM-as-judge | ✅ |
| Task 4 | Production design note | ✅ |
| Bonus | Streamlit TAM/support workspace | ✅ |
| Bonus | Account-brief Server-Sent Events (SSE) stream | ✅ |
| Bonus | Prompt versioning and changelog | ✅ |

The committed local evaluation report is [`eval_report.json`](eval_report.json): **10/10 acceptance cases pass** in deterministic no-secret mode.

---

## Architecture

```text
Raw ticket / JSON ticket
        │
        ▼
Local KB retrieval ──► LangChain structured-output LLM (optional) ──► Pydantic TriageResult
        │                         │
        └── deterministic fallback╰

Account ID ──► account + dataset-relative 90-day tickets ──► risk evidence / quote validation
                                                                  │
                                                                  ▼
                                                LangChain account-brief enrichment (optional)
                                                                  │
                                                                  ▼
                                                normalized Pydantic AccountBrief / SSE stream
```

### Key design choices

- **Retrieval:** The small Markdown corpus is split on `---`, retaining heading metadata. A deterministic lexical retriever prioritizes troubleshooting error-code references and returns the matching path/section.
- **Structured outputs:** `TicketInput`, `TriageResult`, `AccountBrief`, `RiskItem`, and `JudgeResult` are Pydantic models. The configured LangChain path uses function/tool structured output rather than parsing free-form model text.
- **Provider boundary:** `src/common/llm.py` is the only LLM-provider integration point. It supports `openai` and `openai_compatible` settings through environment variables; business services do not import a vendor SDK.
- **Determinism:** The local path is fully deterministic. The LangChain path uses temperature `0`, a fixed seed, stable ticket ordering, and a normalizer that restores canonical account fields, quote evidence, and risk ordering.
- **Safety:** If no LLM credentials are present, or if an LLM call fails, the tool continues using its deterministic local policy. Ticket quotes used as risk evidence are verified against ticket bodies.

---

## Repository layout

```text
src/
├── triage/             # Task 1 ticket-triage service
├── account_brief/      # Task 2 account-health service
├── evals/              # Task 3 evaluation harness and judge
└── common/             # data loading, schemas, retrieval, LLM boundary, prompts
ui/app.py               # Streamlit UI bonus
tests/                  # Unit/API streaming checks
DESIGN_NOTE.md          # Task 4
eval_report.json        # Committed Task 3 output
```

---

## Setup

Requires Python **3.11+**. This repository was verified with Python 3.12 on Windows; the same commands are supported on macOS and Linux.

### Windows PowerShell

```powershell
python -m venv .venv
. .\activate-venv.ps1
python -m pip install -r requirements.txt
```

> `activate-venv.ps1` is provided because some Windows Python distributions omit the standard PowerShell `Activate.ps1` template. If you prefer, no activation is required; use `.\.venv\Scripts\python.exe` directly in every command.

### macOS and Linux (bash/zsh)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `python3` is not available, use the command that refers to your Python 3.11+ installation. To leave the virtual environment on any platform, run `deactivate`.

### Optional LLM configuration

The project works without an API key using local deterministic logic. To enable LangChain structured LLM enrichment and LLM-as-judge evaluation, copy the example file and fill in your own local values:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=your-supported-model
LLM_API_KEY=your-secret-key
LLM_BASE_URL=
LLM_SEED=42
```

`LLM_PROVIDER` can be `openai` or `openai_compatible`; set `LLM_BASE_URL` for a compatible endpoint. Never commit `.env`; it is ignored by Git.

---

## Task 1 - Intelligent ticket triage

### Run the API

```bash
uvicorn src.main:app --reload
```

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

### JSON ticket input

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/triage `
  -ContentType 'application/json' `
  -Body '{"subject":"Production pipeline timeout","body":"DataBridge Pro pipeline returns ERR_CONNECTION_TIMEOUT after 30s and is impacting 47 users."}'
```

**macOS/Linux:**

```bash
curl -X POST http://127.0.0.1:8000/triage \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Production pipeline timeout","body":"DataBridge Pro pipeline returns ERR_CONNECTION_TIMEOUT after 30s and is impacting 47 users."}'
```

### Raw-text ticket input

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/triage/text `
  -ContentType 'text/plain' `
  -Body 'CloudSync SSO reports GROUP_NOT_MAPPED for new users.'
```

**macOS/Linux:**

```bash
curl -X POST http://127.0.0.1:8000/triage/text \
  -H 'Content-Type: text/plain' \
  --data 'CloudSync SSO reports GROUP_NOT_MAPPED for new users.'
```

The result includes:

- a specific product/module area, for example `DataBridge Pro / Pipeline Monitoring`;
- category and P1–P4 urgency;
- classification reasoning;
- matched KB document path/section;
- routed team;
- sendable draft customer response.

Routing policy is deterministic: explicit critical/data-loss/business-stopped signals are P1; urgent failures or material customer impact are P2; moderate issues, workarounds, and requests are P3; otherwise P4. P1 routes to Incident Response; Billing, Onboarding, Feature Request, Integration, and Performance have dedicated teams; remaining cases route to product support.

The callable API is also available:

```python
from src.triage import triage_ticket

result = triage_ticket("DataBridge Pro pipeline ERR_CONNECTION_TIMEOUT after 30s.")
print(result.model_dump())
```

---

## Task 2 - TAM account health brief

**Windows PowerShell:**

```powershell
Invoke-RestMethod http://127.0.0.1:8000/account-brief/ACC-3336
```

**macOS/Linux:**

```bash
curl http://127.0.0.1:8000/account-brief/ACC-3336
```

The brief contains three sections:

1. Executive summary (3–5 sentences)
2. Open risks and flagged issues
3. Recommended TAM talking points

Tickets are filtered to the 90 days before the **maximum `created_at` in the supplied dataset**, never against the current date. Unknown account IDs return a clear HTTP 404 rather than crashing.

Ticket-backed churn/escalation risks contain a direct body quote. Account-level escalation notes are also surfaced as separate evidence.

Callable form:

```python
from src.account_brief import get_account_brief

brief = get_account_brief("ACC-3336")
```

---

## Task 3 - Evaluation harness

Run the standalone harness:

```bash
python -m src.evals.run
```

It regenerates `eval_report.json` and covers:

- 5 ticket-triage cases, including an ambiguous/adversarial ticket;
- 5 account-brief cases, including null-NPS, zero-recent-ticket, and unknown-account scenarios;
- Pydantic schema/enums, KB retrieval, routing, quote provenance, determinism, and empty-state checks;
- pass/fail and a `0–1` quality score per case.

The harness automatically uses the configured LangChain provider for task generation and LLM-as-judge scoring. If no provider is configured, a provider call fails, or structured output is unavailable, it automatically records and uses the deterministic local fallback instead. This keeps the same command runnable in offline CI and local demos:

```bash
python -m src.evals.run
```

Run the unit/API checks with:

```bash
python -m unittest discover -s tests -v
```

---

## Bonus - Streamlit workspace

The non-technical UI has two tabs: a support-agent ticket form and an account-selector TAM brief. It displays routing, KB citations, risk cards, direct evidence quotes, and talking points without requiring a user to read raw API JSON.

```bash
streamlit run ui/app.py
```

Open the local URL Streamlit prints, usually:

```text
http://localhost:8501
```

---

## Bonus - Streaming account brief

The API streams a completed brief section-by-section through Server-Sent Events:

```text
GET /account-brief/{account_id}/stream
```

```powershell
curl.exe -N http://127.0.0.1:8000/account-brief/ACC-3336/stream
```

**macOS/Linux:**

```bash
curl -N http://127.0.0.1:8000/account-brief/ACC-3336/stream
```

The stream emits, in order:

```text
status -> metadata -> executive_summary -> open_risks -> talking_points -> complete
```

Use `curl.exe -N` on Windows or `curl -N` on macOS/Linux rather than Swagger UI to observe event arrival. The endpoint sends an immediate `status` event, then emits each completed brief section without artificial delay.

---

## Prompt versioning

All LLM prompt templates and their changelog entries are in [`src/common/prompts.py`](src/common/prompts.py). Prompt versions are supplied to the LangChain task and judge flows so prompt revisions can be correlated with evaluation changes.

---

## Design note

See [`DESIGN_NOTE.md`](DESIGN_NOTE.md) for the required production discussion of failure modes, latency versus quality, data sensitivity, and scaling to 10× ticket volume.
