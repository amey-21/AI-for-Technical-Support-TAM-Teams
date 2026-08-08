"""Small deterministic BM25-like retriever for the supplied markdown corpus."""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from .data import ROOT

@dataclass(frozen=True)
class Chunk:
    path: str
    heading: str
    text: str

def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_:-]+", text.lower())

@lru_cache
def chunks() -> tuple[Chunk, ...]:
    base = ROOT / "knowledge-base"
    result = []
    for file in sorted(base.rglob("*.md")):
        heading = file.stem
        for section in file.read_text(encoding="utf-8").split("---"):
            found = re.findall(r"^#{1,6}\s+(.+)$", section, re.M)
            if found: heading = " > ".join(found)
            if section.strip(): result.append(Chunk(file.relative_to(ROOT).as_posix(), heading, section.strip()))
    return tuple(result)

def retrieve(query: str) -> Chunk | None:
    query_terms = set(_terms(query))
    if not query_terms: return None
    # Product manuals repeat some errors, but the troubleshooting error-reference
    # table has the prescribed first action. Prefer it for an explicit code.
    error_terms = {term for term in query_terms if "_" in term}
    if error_terms:
        reference_hits = [chunk for chunk in chunks() if "troubleshooting" in chunk.path and error_terms.intersection(_terms(chunk.text))]
        if reference_hits:
            return sorted(reference_hits, key=lambda chunk: (chunk.path, chunk.heading))[0]
    scored = []
    for chunk in chunks():
        text_terms = _terms(chunk.text)
        score = sum(text_terms.count(term) for term in query_terms)
        # Error-code reference tables are the most actionable match. Give an exact
        # code enough weight to beat broad product-name mentions in product docs.
        score += sum(100 for term in query_terms if ("_" in term or term.isupper()) and term in text_terms)
        if score: scored.append((score, chunk.path, chunk.heading, chunk))
    return max(scored)[-1] if scored else None
