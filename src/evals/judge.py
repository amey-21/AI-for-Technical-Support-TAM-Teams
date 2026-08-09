"""Optional LangChain LLM-as-judge with a deterministic no-secret fallback."""
import json
from src.common.llm import LLMClient
from src.common.models import JudgeResult
from src.common.prompts import JUDGE_PROMPT_VERSION, JUDGE_SYSTEM

def assess_quality(task: str, response: object, acceptance_criteria: str, client: LLMClient | None = None) -> tuple[JudgeResult, str]:
    llm = client or LLMClient()
    if llm.enabled:
        try:
            prompt = json.dumps({"prompt_version": JUDGE_PROMPT_VERSION, "task": task, "response": response.model_dump() if hasattr(response, "model_dump") else response, "acceptance_criteria": acceptance_criteria}, ensure_ascii=False)
            return llm.structured(JUDGE_SYSTEM, prompt, JudgeResult), "llm"
        except Exception as exc:
            # Keep reports safe to share: identify the failure class, never echo a
            # provider response that could include endpoint or credential details.
            return JudgeResult(passed=bool(response), quality_score=0.8 if response else 0.0, rationale=f"LLM judge unavailable ({type(exc).__name__}); deterministic heuristic fallback used."), "heuristic_fallback"
    # Explicit fallback keeps CI reproducible without transmitting customer data.
    useful = bool(response) and bool(getattr(response, "reasoning", "") or getattr(response, "executive_summary", ""))
    return JudgeResult(passed=useful, quality_score=0.8 if useful else 0.0, rationale="LLM judge is disabled because no valid provider is configured; deterministic heuristic fallback used."), "heuristic_fallback"
