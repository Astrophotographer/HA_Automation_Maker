from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntitySnap:
    entity_id: str
    domain: str
    device_class: str | None
    area_id: str | None
    area_name: str | None
    state: str
    friendly_name: str
    display_name: str = ""
    device_id: str | None = None
    device_name: str | None = None
    attributes: dict = field(default_factory=dict, compare=False)


@dataclass
class RecipeMatch:
    recipe_id: str
    title: str
    explanation: str
    area_id: str | None
    area_name: str | None
    trigger_entity_ids: list[str]
    action_entity_ids: list[str]
    recipe: dict
