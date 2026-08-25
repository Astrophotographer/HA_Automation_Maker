"""Pure builders for the Dashboard web panel JSON payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_BAD_STATES = frozenset({"unavailable", "unknown", "none", ""})

_ACTIONS = frozenset(
    {
        "approve",
        "deploy",
        "later",
        "dismiss",
        "delete",
        "resend",
        "resend_all",
        "scan",
    }
)


def build_device_row(
    entity_id: str,
    name: str,
    area: str,
    state: str,
    automation_count: int,
    suggestion_count: int,
) -> dict[str, Any]:
    st = "" if state is None else str(state)
    return {
        "entity_id": entity_id,
        "name": name,
        "area": area or "기타",
        "state": st,
        "ok": st.casefold() not in _BAD_STATES,
        "automation_count": int(automation_count),
        "suggestion_count": int(suggestion_count),
    }


def build_summary(
    *,
    synced_at: str,
    devices: list[dict[str, Any]],
    pending_count: int,
) -> dict[str, Any]:
    anomaly = sum(1 for d in devices if not d.get("ok", True))
    return {
        "synced_at": synced_at,
        "device_count": len(devices),
        "anomaly_count": anomaly,
        "pending_count": int(pending_count),
        "devices": devices,
    }


def list_automations(
    suggestions: list[dict[str, Any]],
    *,
    include_dismissed: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in suggestions:
        status = str(s.get("status") or "")
        if status == "dismissed" and not include_dismissed:
            continue
        if status not in {"pending", "previewed", "deployed", "dismissed"}:
            continue
        auto = s.get("automation") or {}
        explanation = str(s.get("behavior") or s.get("explanation") or "")[:240]
        item: dict[str, Any] = {
            "id": s.get("id"),
            "title": s.get("title") or auto.get("alias") or s.get("id"),
            "status": status,
            "source": s.get("source"),
            "explanation": explanation,
            "automation_id": auto.get("id"),
            "alias": auto.get("alias") or s.get("title"),
        }
        if s.get("confidence") is not None:
            try:
                item["score"] = float(s["confidence"])
            except (TypeError, ValueError):
                pass
        out.append(item)
    return out


def build_log_lines(
    events: list[Any],
    *,
    names: dict[str, str],
    start_n: int = 1,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        eid = getattr(ev, "entity_id", None) or ""
        name = names.get(eid, eid)
        old = getattr(ev, "old_state", None)
        new = getattr(ev, "new_state", None)
        actor = getattr(ev, "actor", None) or "unknown"
        ts_raw = getattr(ev, "ts", None)
        if isinstance(ts_raw, (int, float)):
            ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc).isoformat()
        else:
            ts = str(ts_raw or "")
        msg = f"{name} {eid} {old}→{new} actor={actor}"
        lines.append(
            {
                "n": int(start_n) + i,
                "ts": ts,
                "entity_id": eid,
                "name": name,
                "old": old,
                "new": new,
                "actor": actor,
                "msg": msg,
            }
        )
    return lines


def build_reasons(
    suggestions: list[dict[str, Any]],
    *,
    min_confidence: float,
    min_support: int,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for s in suggestions:
        status = str(s.get("status") or "")
        if status not in {"pending", "previewed", "deployed", "dismissed"}:
            continue
        score = None
        if s.get("confidence") is not None:
            try:
                score = float(s["confidence"])
            except (TypeError, ValueError):
                score = None
        support = s.get("support")
        try:
            support_n = int(support) if support is not None else None
        except (TypeError, ValueError):
            support_n = None
        above = False
        if score is not None:
            above = score >= float(min_confidence)
        items.append(
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "status": status,
                "source": s.get("source"),
                "explanation": str(s.get("behavior") or s.get("explanation") or "")[
                    :240
                ],
                "score": score,
                "support": support_n,
                "above_threshold": above,
            }
        )
    return {
        "thresholds": {
            "min_confidence": float(min_confidence),
            "min_support": int(min_support),
        },
        "items": items,
    }


def normalize_action(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k not in _ACTIONS:
        raise ValueError(f"unknown action: {kind}")
    return k
