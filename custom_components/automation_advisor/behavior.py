"""Human-readable condition/action text for suggestions (no Home Assistant imports)."""

from __future__ import annotations

from .models import RecipeMatch

_ACTION_LABELS = {
    "light.turn_on": "켜기",
    "light.turn_off": "끄기",
    "fan.turn_on": "켜기",
    "fan.turn_off": "끄기",
    "switch.turn_on": "켜기",
    "switch.turn_off": "끄기",
    "homeassistant.turn_on": "켜기",
    "homeassistant.turn_off": "끄기",
    "persistent_notification.create": "알림 보내기",
}


def _label(entity_id: str, names: dict[str, str] | None) -> str:
    """Prefer UI/Korean friendly name; avoid romanized entity_id slug as the title."""
    name = (names or {}).get(entity_id)
    if not name or name == entity_id:
        # Last resort: keep entity_id readable, but do not pretend it's a Korean label.
        return f"`{entity_id}`"
    return f"**{name}** (`{entity_id}`)"


def _join_labels(entity_ids: list[str], names: dict[str, str] | None) -> str:
    if not entity_ids:
        return "(없음)"
    return ", ".join(_label(eid, names) for eid in entity_ids)


def _format_duration(for_spec: dict | None) -> str:
    if not for_spec:
        return ""
    if "minutes" in for_spec:
        return f"{for_spec['minutes']}분"
    if "seconds" in for_spec:
        return f"{for_spec['seconds']}초"
    if "hours" in for_spec:
        return f"{for_spec['hours']}시간"
    return str(for_spec)


_SUN_EVENTS = {
    "sunset": "일몰",
    "sunrise": "일출",
}


def describe_match_behavior(
    match: RecipeMatch, names: dict[str, str] | None = None
) -> str:
    """Concrete Korean summary: which sensor/condition → which action/entities."""
    spec = match.recipe.get("compile") or {}
    trigger = dict(spec.get("trigger") or {})
    platform = trigger.get("platform", "state")
    triggers = _join_labels(match.trigger_entity_ids, names)
    actions = _join_labels(match.action_entity_ids, names)
    action_name = str(spec.get("action") or "")
    action_verb = _ACTION_LABELS.get(action_name, action_name)

    if platform == "state":
        to_state = trigger.get("to")
        duration = _format_duration(trigger.get("for"))
        if duration and to_state is not None:
            when = f"{triggers}이(가) **{to_state}** 상태로 **{duration}** 유지되면"
        elif to_state is not None:
            when = f"{triggers}이(가) **{to_state}** 이(가) 되면"
        else:
            when = f"{triggers} 상태가 바뀌면"
    elif platform == "numeric_state":
        parts = []
        if "above" in trigger:
            parts.append(f"**{trigger['above']}** 초과")
        if "below" in trigger:
            parts.append(f"**{trigger['below']}** 미만")
        thresh = " · ".join(parts) or "임계값"
        when = f"{triggers}이(가) {thresh}이면"
    elif platform == "sun":
        event = str(trigger.get("event", "sunset"))
        when = f"**{_SUN_EVENTS.get(event, event)}**이면"
    else:
        when = f"트리거({platform}): {triggers}"

    if action_name == "persistent_notification.create":
        title = spec.get("notify_title") or "알림"
        then = f"알림 보내기 — 「{title}」"
    elif match.action_entity_ids:
        then = f"{actions} **{action_verb}**"
    else:
        then = action_verb or action_name

    area = f"（{match.area_name}）" if match.area_name else ""
    return f"**조건{area}:** {when}\n**동작:** {then}"


def describe_automation_behavior(
    automation: dict, names: dict[str, str] | None = None
) -> str | None:
    """Best-effort summary from a compiled automation dict (for older suggestions)."""
    triggers = automation.get("trigger") or []
    actions = automation.get("action") or []
    if not triggers:
        return None
    trig = triggers[0]
    platform = trig.get("platform", "state")
    entity_ids = trig.get("entity_id") or []
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    trigger_labels = _join_labels(list(entity_ids), names) if entity_ids else ""

    if platform == "state":
        to_state = trig.get("to")
        duration = _format_duration(trig.get("for"))
        if duration and to_state is not None:
            when = f"{trigger_labels}이(가) **{to_state}** 상태로 **{duration}** 유지되면"
        elif to_state is not None:
            when = f"{trigger_labels}이(가) **{to_state}** 이(가) 되면"
        else:
            when = f"{trigger_labels} 상태가 바뀌면"
    elif platform == "sun":
        event = str(trig.get("event", "sunset"))
        when = f"**{_SUN_EVENTS.get(event, event)}**이면"
    elif platform == "numeric_state":
        when = f"{trigger_labels} numeric_state"
    else:
        when = f"{platform}"

    then = "동작"
    if actions:
        step = actions[0]
        full = str(step.get("action") or step.get("service") or "")
        verb = _ACTION_LABELS.get(full, full)
        target = (step.get("target") or {}).get("entity_id") or []
        if isinstance(target, str):
            target = [target]
        if full == "persistent_notification.create":
            title = (step.get("data") or {}).get("title") or "알림"
            then = f"알림 보내기 — 「{title}」"
        elif target:
            then = f"{_join_labels(list(target), names)} **{verb}**"
        else:
            then = verb

    return f"**조건:** {when}\n**동작:** {then}"


def suggestion_detail_text(suggestion: dict, names: dict[str, str] | None = None) -> str:
    """Prefer stored behavior; else derive from automation; else explanation."""
    behavior = suggestion.get("behavior")
    if behavior:
        return str(behavior)
    merged = {**(suggestion.get("entity_names") or {}), **(names or {})}
    auto = suggestion.get("automation") or {}
    derived = describe_automation_behavior(auto, merged)
    if derived:
        return derived
    return str(suggestion.get("explanation") or "")
