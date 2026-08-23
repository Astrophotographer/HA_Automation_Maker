"""Deterministic compiler: structured match → Home Assistant automation dict.

YAML is never invented by an LLM.
"""

from __future__ import annotations

from .models import RecipeMatch


def compile_suggestion(
    match: RecipeMatch,
    *,
    suggestion_id: str,
    trial: bool = True,
) -> dict:
    spec = match.recipe.get("compile") or {}
    trigger_spec = dict(spec.get("trigger") or {"platform": "state", "to": "on"})
    platform = trigger_spec.pop("platform", "state")
    trigger: dict = {"platform": platform, **trigger_spec}
    if platform in {"state", "numeric_state"}:
        trigger["entity_id"] = list(match.trigger_entity_ids)

    action_name = str(spec.get("action") or "homeassistant.turn_on")
    if action_name == "persistent_notification.create":
        entity = match.trigger_entity_ids[0] if match.trigger_entity_ids else ""
        action = {
            "action": "persistent_notification.create",
            "data": {
                "title": str(spec.get("notify_title") or match.title),
                "message": str(spec.get("notify_message") or match.explanation).format(
                    entity=entity,
                    area=match.area_name or "",
                ),
                "notification_id": f"advisor_{suggestion_id}",
            },
        }
    else:
        action = {
            "action": action_name,
            "target": {"entity_id": list(match.action_entity_ids)},
        }

    alias_area = f"{match.area_name} " if match.area_name else ""
    auto_id = f"advisor_{match.recipe_id}_{suggestion_id}"
    return {
        "id": auto_id,
        "alias": f"Advisor: {alias_area}{match.title}".strip(),
        "description": f"[Advisor:{suggestion_id}] {match.explanation}",
        "initial_state": not trial,
        "trigger": [trigger],
        "condition": [],
        "action": [action],
        "mode": "single",
    }


def action_to_service_call(automation: dict) -> tuple[str, str, dict]:
    """Turn compiler action step into (domain, service, data) for a one-shot run."""
    steps = automation.get("action") or []
    if not steps:
        raise ValueError("automation has no action")
    step = steps[0]
    full = str(step.get("action") or step.get("service") or "")
    if "." not in full:
        raise ValueError(f"invalid action: {full!r}")
    domain, service = full.split(".", 1)
    data = dict(step.get("data") or {})
    target = step.get("target") or {}
    if "entity_id" in target:
        data["entity_id"] = target["entity_id"]
    return domain, service, data
