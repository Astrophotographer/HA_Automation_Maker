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

# Prefer these domains when picking a representative state for a device group.
_PRIMARY_DOMAINS = (
    "light",
    "switch",
    "climate",
    "cover",
    "fan",
    "media_player",
    "lock",
    "binary_sensor",
)


def build_device_row(
    entity_id: str,
    name: str,
    area: str,
    state: str,
    automation_count: int,
    suggestion_count: int,
    *,
    device_id: str | None = None,
    device_name: str | None = None,
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
        "device_id": device_id,
        "device_name": device_name,
    }


def _entity_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    domain = str(row.get("entity_id") or "").split(".", 1)[0]
    try:
        rank = _PRIMARY_DOMAINS.index(domain)
    except ValueError:
        rank = len(_PRIMARY_DOMAINS)
    return (rank, str(row.get("name") or row.get("entity_id") or ""))


def group_devices(entity_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse entity rows into HA device groups (one card per physical device)."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in entity_rows:
        did = row.get("device_id")
        key = str(did) if did else f"entity:{row.get('entity_id')}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)

    devices: list[dict[str, Any]] = []
    for key in order:
        ents = sorted(buckets[key], key=_entity_sort_key)
        primary = ents[0]
        ok = all(bool(e.get("ok", True)) for e in ents)
        bad = next((e for e in ents if not e.get("ok", True)), None)
        state = str((bad or primary).get("state") or "")
        device_name = next(
            (str(e["device_name"]).strip() for e in ents if e.get("device_name")),
            None,
        )
        name = device_name or str(primary.get("name") or primary.get("entity_id") or key)
        area = str(primary.get("area") or "기타")
        devices.append(
            {
                "device_id": primary.get("device_id"),
                "name": name,
                "area": area,
                "state": state,
                "ok": ok,
                "automation_count": sum(int(e.get("automation_count") or 0) for e in ents),
                "suggestion_count": sum(int(e.get("suggestion_count") or 0) for e in ents),
                "entity_count": len(ents),
                "entities": [
                    {
                        "entity_id": e.get("entity_id"),
                        "name": e.get("name"),
                        "state": e.get("state"),
                        "ok": bool(e.get("ok", True)),
                        "automation_count": int(e.get("automation_count") or 0),
                        "suggestion_count": int(e.get("suggestion_count") or 0),
                    }
                    for e in ents
                ],
            }
        )
    return devices


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


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _reason_item(
    s: dict[str, Any],
    *,
    min_confidence: float,
    min_support: int,
    min_lift: float,
) -> dict[str, Any]:
    confidence = _as_float(s.get("confidence"))
    support_n = _as_int(s.get("support"))
    lift = _as_float(s.get("lift"))
    checks: list[bool] = []
    if confidence is not None:
        checks.append(confidence >= float(min_confidence))
    if support_n is not None:
        checks.append(support_n >= int(min_support))
    if lift is not None:
        checks.append(lift >= float(min_lift))
    above = all(checks) if checks else bool(s.get("above_threshold", True))
    return {
        "id": s.get("id"),
        "title": s.get("title"),
        "status": s.get("status"),
        "source": s.get("source"),
        "explanation": str(s.get("behavior") or s.get("explanation") or "")[:240],
        "score": confidence,
        "confidence": confidence,
        "support": support_n,
        "lift": lift,
        "above_threshold": above,
        "has_metrics": confidence is not None
        or support_n is not None
        or lift is not None,
    }


def build_reasons(
    suggestions: list[dict[str, Any]],
    *,
    min_confidence: float,
    min_support: int,
    min_lift: float = 1.2,
    habit: dict[str, Any] | None = None,
    preview: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for s in suggestions:
        status = str(s.get("status") or "")
        if status not in {"pending", "previewed", "deployed", "dismissed"}:
            continue
        items.append(
            _reason_item(
                s,
                min_confidence=min_confidence,
                min_support=min_support,
                min_lift=min_lift,
            )
        )

    # Habit patterns discovered but not yet promoted to suggestions (observe gate).
    seen_titles = {str(it.get("title") or "") for it in items if it.get("has_metrics")}
    for p in preview or []:
        title = str(p.get("title") or "")
        if title and title in seen_titles:
            continue
        row = dict(p)
        row.setdefault("status", "preview")
        row.setdefault("source", "habit_preview")
        row.setdefault("id", f"preview_{len(items)}")
        items.append(
            _reason_item(
                row,
                min_confidence=min_confidence,
                min_support=min_support,
                min_lift=min_lift,
            )
        )

    return {
        "thresholds": {
            "min_confidence": float(min_confidence),
            "min_support": int(min_support),
            "min_lift": float(min_lift),
        },
        "habit": habit or {},
        "items": items,
    }


def normalize_action(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k not in _ACTIONS:
        raise ValueError(f"unknown action: {kind}")
    return k
