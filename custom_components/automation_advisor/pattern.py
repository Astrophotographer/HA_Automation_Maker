"""Pattern engine — support / confidence / lift from learnable local events."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .actor import LEARNABLE
from .const import (
    MIN_PATTERN_CONFIDENCE,
    MIN_PATTERN_LIFT,
    MIN_PATTERN_SUPPORT,
    PATTERN_WINDOW_SECONDS,
)
from .event_store import StoredEvent


@dataclass(frozen=True)
class HabitPattern:
    trigger_entity_id: str
    trigger_to: str
    action_entity_id: str
    action_to: str
    support: int
    confidence: float
    lift: float
    title: str
    explanation: str

    @property
    def recipe_id(self) -> str:
        return f"habit_{self.trigger_entity_id}_{self.action_entity_id}".replace(".", "_")

    @property
    def entities(self) -> list[str]:
        return sorted({self.trigger_entity_id, self.action_entity_id})


def _action_service(domain: str, new_state: str) -> str:
    if new_state in {"on", "open", "playing", "home"}:
        return f"{domain}.turn_on" if domain != "cover" else "cover.open_cover"
    if new_state in {"off", "closed", "idle", "not_home"}:
        return f"{domain}.turn_off" if domain != "cover" else "cover.close_cover"
    return "homeassistant.turn_on"


def discover_patterns(
    events: list[StoredEvent],
    *,
    window_seconds: int = PATTERN_WINDOW_SECONDS,
    min_support: int = MIN_PATTERN_SUPPORT,
    min_confidence: float = MIN_PATTERN_CONFIDENCE,
    min_lift: float = MIN_PATTERN_LIFT,
) -> list[HabitPattern]:
    learnable = [e for e in events if e.actor in LEARNABLE]
    if len(learnable) < min_support * 2:
        return []

    pair_counts: Counter[tuple[str, str, str, str]] = Counter()
    trigger_counts: Counter[tuple[str, str]] = Counter()
    action_counts: Counter[tuple[str, str]] = Counter()

    by_time = sorted(learnable, key=lambda e: e.ts)
    n = len(by_time)
    for i, a in enumerate(by_time):
        trigger_counts[(a.entity_id, a.new_state)] += 1
        action_counts[(a.entity_id, a.new_state)] += 1
        for j in range(i + 1, n):
            b = by_time[j]
            if b.ts - a.ts > window_seconds:
                break
            if a.entity_id == b.entity_id:
                continue
            # Same area when both known; otherwise still allow (physical rooms may lack area).
            if a.area_id and b.area_id and a.area_id != b.area_id:
                continue
            key = (a.entity_id, a.new_state, b.entity_id, b.new_state)
            pair_counts[key] += 1

    total_actions = sum(action_counts.values()) or 1
    patterns: list[HabitPattern] = []

    for (trig_e, trig_to, act_e, act_to), support in pair_counts.items():
        if support < min_support:
            continue
        trig_n = trigger_counts[(trig_e, trig_to)] or 1
        confidence = support / trig_n
        if confidence < min_confidence:
            continue
        p_b = action_counts[(act_e, act_to)] / total_actions
        lift = confidence / p_b if p_b > 0 else 0.0
        if lift < min_lift:
            continue
        title = f"{trig_e} 다음에 {act_e}"
        explanation = (
            f"최근 수동 조작에서 `{trig_e}`→`{trig_to}` 직후 "
            f"`{act_e}`→`{act_to}` 가 {support}회 반복됐습니다 "
            f"(confidence {confidence:.0%}, lift {lift:.1f})."
        )
        patterns.append(
            HabitPattern(
                trigger_entity_id=trig_e,
                trigger_to=trig_to,
                action_entity_id=act_e,
                action_to=act_to,
                support=support,
                confidence=confidence,
                lift=lift,
                title=title,
                explanation=explanation,
            )
        )

    patterns.sort(key=lambda p: (p.lift, p.confidence, p.support), reverse=True)
    return patterns


def habit_to_automation(
    pattern: HabitPattern,
    *,
    suggestion_id: str,
    trial: bool = True,
    domain_for_action: str | None = None,
) -> dict:
    domain = domain_for_action or pattern.action_entity_id.split(".", 1)[0]
    service = _action_service(domain, pattern.action_to)
    # Prefer explicit turn_on/off service names for compiler one-shot.
    if service.endswith(".turn_on") or service.endswith(".turn_off"):
        action = {
            "action": service,
            "target": {"entity_id": [pattern.action_entity_id]},
        }
    elif service.startswith("cover."):
        action = {
            "action": service,
            "target": {"entity_id": [pattern.action_entity_id]},
        }
    else:
        action = {
            "action": "homeassistant.turn_on",
            "target": {"entity_id": [pattern.action_entity_id]},
        }

    auto_id = f"advisor_habit_{suggestion_id}"
    return {
        "id": auto_id,
        "alias": f"Advisor: {pattern.title}",
        "description": f"[Advisor:{suggestion_id}] {pattern.explanation}",
        "initial_state": not trial,
        "trigger": [
            {
                "platform": "state",
                "entity_id": [pattern.trigger_entity_id],
                "to": pattern.trigger_to,
            }
        ],
        "condition": [],
        "action": [action],
        "mode": "single",
    }
