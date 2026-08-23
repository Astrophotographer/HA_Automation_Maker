"""Match builtin recipes against a local device snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from .models import EntitySnap, RecipeMatch

_RECIPES_PATH = Path(__file__).with_name("recipes.json")


def load_recipes(path: Path | None = None) -> list[dict]:
    data = json.loads((path or _RECIPES_PATH).read_text(encoding="utf-8"))
    return list(data.get("recipes") or [])


def _parse_need(need: str) -> tuple[str, tuple[str, ...]]:
    if "." in need:
        domain, classes = need.split(".", 1)
        return domain, tuple(classes.split("|"))
    return need, ()


def _need_matches(entity: EntitySnap, need: str) -> bool:
    domain, classes = _parse_need(need)
    if entity.domain != domain:
        return False
    if not classes:
        return True
    return (entity.device_class or "") in classes


def match_recipes(recipes: list[dict], inventory: list[EntitySnap]) -> list[RecipeMatch]:
    matches: list[RecipeMatch] = []

    for recipe in recipes:
        same_area = bool(recipe.get("same_area"))
        needs: list[str] = list(recipe.get("need") or [])
        if same_area:
            area_ids = {e.area_id for e in inventory if e.area_id}
            scopes = [(area_id, [e for e in inventory if e.area_id == area_id]) for area_id in area_ids]
        else:
            scopes = [(None, inventory)]

        for area_id, scope in scopes:
            slots: list[list[EntitySnap]] = []
            ok = True
            for need in needs:
                found = [e for e in scope if _need_matches(e, need)]
                if not found:
                    ok = False
                    break
                slots.append(found)
            if not ok:
                continue

            compile_spec = recipe.get("compile") or {}
            trigger_idx = int(compile_spec.get("trigger_index", 0))
            action_idx = compile_spec.get("action_index")
            trigger_ids = [e.entity_id for e in slots[trigger_idx]]
            action_ids = (
                [e.entity_id for e in slots[int(action_idx)]]
                if action_idx is not None
                else []
            )
            area_name = next((e.area_name for e in scope if e.area_id == area_id and e.area_name), None)
            explanation = str(recipe.get("explanation") or recipe.get("title") or "").format(
                area=area_name or "이 집",
                entity=trigger_ids[0] if trigger_ids else "",
            )
            matches.append(
                RecipeMatch(
                    recipe_id=str(recipe["id"]),
                    title=str(recipe.get("title") or recipe["id"]),
                    explanation=explanation,
                    area_id=area_id,
                    area_name=area_name,
                    trigger_entity_ids=trigger_ids,
                    action_entity_ids=action_ids,
                    recipe=recipe,
                )
            )
    return matches
