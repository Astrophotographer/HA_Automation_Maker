"""Tests for concrete condition/action behavior text."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from automation_advisor.behavior import (  # noqa: E402
    describe_automation_behavior,
    describe_match_behavior,
)
from automation_advisor.catalog import load_recipes, match_recipes  # noqa: E402
from automation_advisor.models import EntitySnap  # noqa: E402
from automation_advisor.recommender import recommend  # noqa: E402


def _snap(
    entity_id: str,
    *,
    device_class: str | None = None,
    area_id: str | None = "living",
    area_name: str = "거실",
    friendly_name: str | None = None,
    display_name: str | None = None,
) -> EntitySnap:
    domain = entity_id.split(".", 1)[0]
    label = display_name or friendly_name or entity_id
    return EntitySnap(
        entity_id=entity_id,
        domain=domain,
        device_class=device_class,
        area_id=area_id,
        area_name=area_name,
        state="off",
        friendly_name=friendly_name or label,
        display_name=label,
    )


class BehaviorTests(unittest.TestCase):
    def test_occupancy_off_mentions_sensor_minutes_and_light(self) -> None:
        inventory = [
            _snap(
                "binary_sensor.living_motion",
                device_class="motion",
                friendly_name="거실 모션",
                display_name="모션",
            ),
            _snap("light.living_lamp", friendly_name="거실 램프", display_name="램프"),
        ]
        match = next(
            m
            for m in match_recipes(load_recipes(), inventory)
            if m.recipe_id == "occupancy_light_off"
        )
        names = {e.entity_id: e.display_name for e in inventory}
        text = describe_match_behavior(match, names)
        self.assertIn("모션", text)
        self.assertIn("10분", text)
        self.assertIn("off", text)
        self.assertIn("램프", text)
        self.assertIn("끄기", text)
        self.assertNotIn("living_motion", text)
        self.assertNotIn("`", text)

    def test_recommend_includes_behavior_field(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion", display_name="모션"),
            _snap("light.living_lamp", display_name="램프"),
        ]
        suggestions = recommend(inventory, community_rates={})
        off = next(s for s in suggestions if s["recipe_id"] == "occupancy_light_off")
        self.assertIn("behavior", off)
        self.assertIn("10분", off["behavior"])
        self.assertIn("10분", off["explanation"])

    def test_describe_from_compiled_automation(self) -> None:
        auto = {
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": ["binary_sensor.cam_motion"],
                    "to": "off",
                    "for": {"minutes": 10},
                }
            ],
            "action": [
                {
                    "action": "light.turn_off",
                    "target": {"entity_id": ["light.a", "light.b"]},
                }
            ],
        }
        text = describe_automation_behavior(
            auto, {"binary_sensor.cam_motion": "캠 모션", "light.a": "A", "light.b": "B"}
        )
        assert text is not None
        self.assertIn("캠 모션", text)
        self.assertIn("10분", text)
        self.assertIn("A", text)
        self.assertIn("끄기", text)


if __name__ == "__main__":
    unittest.main()
