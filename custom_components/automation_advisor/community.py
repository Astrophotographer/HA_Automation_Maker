"""Community catalog rates — stub JSON only (no remote upload)."""

from __future__ import annotations

import json
from pathlib import Path

_STUB_PATH = Path(__file__).with_name("community_stub.json")


def load_community_rates(path: Path | None = None) -> dict[str, dict]:
    data = json.loads((path or _STUB_PATH).read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in data.get("recipes") or []:
        rid = row.get("id")
        if rid:
            out[str(rid)] = row
    return out


def enrich_explanation(base: str, recipe_id: str, rates: dict[str, dict] | None) -> str:
    if not rates or recipe_id not in rates:
        return base
    row = rates[recipe_id]
    accepted = row.get("accepted")
    homes = row.get("homes_with_need")
    if accepted is None:
        return base
    pct = int(round(float(accepted) * 100))
    if homes:
        return f"{base} (비슷한 환경 스텁: {homes}곳 중 약 {pct}%가 사용)"
    return f"{base} (비슷한 환경 스텁: 약 {pct}%가 사용)"
