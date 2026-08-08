import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

@lru_cache
def tickets() -> list[dict]:
    return json.loads((ROOT / "data" / "tickets.json").read_text(encoding="utf-8"))

@lru_cache
def accounts() -> list[dict]:
    return json.loads((ROOT / "data" / "accounts.json").read_text(encoding="utf-8"))

def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def dataset_max_date() -> datetime:
    return max(parse_date(t["created_at"]) for t in tickets())

def account_tickets(account_id: str, days: int = 90) -> list[dict]:
    cutoff = dataset_max_date().timestamp() - days * 86400
    return [t for t in tickets() if t.get("account_id") == account_id and parse_date(t["created_at"]).timestamp() >= cutoff]
