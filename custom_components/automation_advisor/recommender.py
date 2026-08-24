"""Rank catalog/rule matches and habit patterns; drop conflicts and unsafe actions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .behavior import describe_match_behavior
from .catalog import load_recipes, match_recipes
from .community import enrich_explanation, load_community_rates
from .compiler import compile_suggestion
from .models import EntitySnap
from .pattern import HabitPattern, habit_to_automation
from .safety import is_blocked


def _conflicts(match_entities: set[str], existing_entity_sets: list[set[str]]) -> bool:
    if len(match_entities) < 2:
        for existing in existing_entity_sets:
            if match_entities and match_entities <= existing:
                return True
        return False
    for existing in existing_entity_sets:
        if match_entities <= existing:
            return True
    return False


def recommend(
    inventory: list[EntitySnap],
    *,
    existing_entity_sets: list[set[str]] | None = None,
    trial: bool = True,
    recipes: list[dict] | None = None,
    community_rates: dict[str, dict] | None = None,
    habit_patterns: list[HabitPattern] | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> list[dict]:
    existing_entity_sets = existing_entity_sets or []
    recipes = recipes if recipes is not None else load_recipes()
    if community_rates is None:
        community_rates = {}
    names = {e.entity_id: e.friendly_name for e in inventory}
    out: list[dict] = []
    seen: set[tuple] = set()

    for match in match_recipes(recipes, inventory):
        if is_blocked(match.action_entity_ids):
            continue
        entities = set(match.trigger_entity_ids) | set(match.action_entity_ids)
        key = (match.recipe_id, match.area_id, tuple(sorted(entities)))
        if key in seen:
            continue
        seen.add(key)
        if _conflicts(entities, existing_entity_sets):
            continue
        suggestion_id = uuid.uuid4().hex[:8]
        behavior = describe_match_behavior(match, names)
        community = enrich_explanation("", match.recipe_id, community_rates).strip()
        explanation = behavior if not community else f"{behavior}\n\n{community}"
        out.append(
            {
                "id": suggestion_id,
                "recipe_id": match.recipe_id,
                "source": "catalog",
                "title": match.title,
                "explanation": explanation,
                "behavior": behavior,
                "area_id": match.area_id,
                "area_name": match.area_name,
                "entities": sorted(entities),
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "deployed_at": None,
                "feedback": None,
                "trial": trial,
                "automation": compile_suggestion(
                    match, suggestion_id=suggestion_id, trial=trial
                ),
            }
        )

    for pattern in habit_patterns or []:
        if is_blocked([pattern.action_entity_id]):
            continue
        entities = set(pattern.entities)
        key = (pattern.recipe_id, None, tuple(sorted(entities)))
        if key in seen:
            continue
        seen.add(key)
        if _conflicts(entities, existing_entity_sets):
            continue
        suggestion_id = uuid.uuid4().hex[:8]
        explanation = pattern.explanation
        if llm_base_url or llm_api_key:
            from .explain import explain_pattern

            explanation = explain_pattern(
                base_url=llm_base_url,
                model=llm_model,
                api_key=llm_api_key,
                title=pattern.title,
                facts=pattern.explanation,
                fallback=pattern.explanation,
            )
        out.append(
            {
                "id": suggestion_id,
                "recipe_id": pattern.recipe_id,
                "source": "habit",
                "title": pattern.title,
                "explanation": explanation,
                "area_id": None,
                "area_name": None,
                "entities": sorted(entities),
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "deployed_at": None,
                "feedback": None,
                "trial": trial,
                "support": pattern.support,
                "confidence": pattern.confidence,
                "lift": pattern.lift,
                "automation": habit_to_automation(
                    pattern, suggestion_id=suggestion_id, trial=trial
                ),
            }
        )

    return out
