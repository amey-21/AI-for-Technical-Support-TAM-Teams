# Design note

## 1. Failure modes

**Misclassification or unsafe routing** is the most immediate operational risk. A short ticket can describe both a feature request and a performance problem, while words such as “critical” can be emotional rather than an outage indicator. The service detects this through the evaluation harness’s ambiguous ticket, production sampling of agent overrides, and monitoring of category/priority disagreement rates. It mitigates risk by retaining a concise reason, routing P1 cases to Incident Response, and presenting the result as a draft for an agent rather than automatically changing a ticket. A future LLM-enabled deployment should use calibrated confidence and send low-confidence cases to a human queue.

**Retrieval misses or stale documentation** can produce an unhelpful response even when the classification is right. The implementation chunks only the supplied Markdown files on `---`, preserves headings, and uses a deterministic term-based ranking. Tests cover known error-code retrieval. In production, track no-match rates, clicked/helpful response feedback, and document revision timestamps. Mitigate with versioned KB ingestion, regression questions per document, and lexical-plus-embedding retrieval with reranking once the corpus is larger.

**Data-quality gaps** are expected because ticket account IDs do not always join to an account. The account-brief function returns `None` and the API returns a clear 404 rather than dereferencing missing data. Null NPS and zero-recent-ticket accounts are explicit evaluation cases. Operationally, measure join failure and null-field rates, alert on unexpected shifts, and reconcile upstream CRM/support identifiers. The brief also uses the maximum synthetic ticket timestamp, rather than wall-clock time, so historical demos and batch reruns remain stable.

## 2. Latency versus quality

This implementation deliberately uses a local deterministic policy and lightweight lexical retrieval as the default. It avoids network latency and makes account briefs reproducible, but it is less nuanced than a model interpreting natural language. The LangChain `LLMClient` is isolated and supports Pydantic tool/function structured output, temperature zero, a fixed seed, and an environment-selected provider/model for a higher-quality deployment. The same boundary powers an optional LLM-as-judge in the evaluation harness. If latency became the hard constraint, pre-index KB term vectors at startup, cache repeated triage results by normalized ticket text, and keep the deterministic classifier for the first response; asynchronous LLM enrichment could update the agent view later.

## 3. Data sensitivity

Tickets and account records may include contacts, company data, and incident details. All provided data stays on disk; retrieval uses only the local corpus. The default path calls no external API. If `LLM_PROVIDER=openai` is deliberately configured, the wrapper is the only egress point, making it practical to add field-level redaction, an allowlist of prompt fields, audit logs without body text, retention controls, and a customer-approved regional provider. Credentials are environment variables only; `.env.example` includes names but no values.

## 4. Scaling

At 10× ticket volume, repeated JSON filtering and linear retrieval are the first weak points: every account brief scans the ticket list, while every triage scores all KB chunks. The code is appropriate for the supplied small corpus but should then move data to a database indexed by `(account_id, created_at)`, precompute account-health aggregates, and use an inverted index/vector store with background KB ingestion. API workers should be stateless, with caching and rate limits around any LLM provider. Evaluation fixtures should remain deterministic and run in CI before changing prompts or routing rules.
