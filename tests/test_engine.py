"""Pure-Python tests for the Automation Advisor v1 engine."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from datetime import datetime, timedelta, timezone  # noqa: E402

from automation_advisor.actor import (  # noqa: E402
    ACTOR_AUTOMATION,
    ACTOR_HUMAN,
    classify_actor,
    is_learnable,
)
from automation_advisor.actions import KIND_RUN, parse_action  # noqa: E402
from automation_advisor.catalog import EntitySnap, load_recipes, match_recipes  # noqa: E402
from automation_advisor.community import enrich_explanation, load_community_rates  # noqa: E402
from automation_advisor.compiler import action_to_service_call, compile_suggestion  # noqa: E402
from automation_advisor.const import DISMISS_COOLDOWN_DAYS, DOMAIN  # noqa: E402
from automation_advisor.event_store import EventStore, StoredEvent  # noqa: E402
from automation_advisor.pattern import discover_patterns, habit_to_automation  # noqa: E402
from automation_advisor.safety import BLOCKED_ACTION_DOMAINS, is_blocked  # noqa: E402
from automation_advisor.recommender import recommend  # noqa: E402
from automation_advisor.suggestion_policy import blocks_resuggestion  # noqa: E402


def _snap(
    entity_id: str,
    *,
    device_class: str | None = None,
    area_id: str | None = "living",
    area_name: str = "Living room",
    state: str = "off",
) -> EntitySnap:
    domain = entity_id.split(".", 1)[0]
    return EntitySnap(
        entity_id=entity_id,
        domain=domain,
        device_class=device_class,
        area_id=area_id,
        area_name=area_name,
        state=state,
        friendly_name=entity_id.split(".", 1)[1].replace("_", " ").title(),
    )


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recipes = load_recipes()

    def test_loads_builtin_catalog(self) -> None:
        ids = {r["id"] for r in self.recipes}
        self.assertIn("occupancy_light", ids)

    def test_occupancy_light_same_area(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion"),
            _snap("light.living_lamp"),
        ]
        matches = match_recipes(self.recipes, inventory)
        occ = [m for m in matches if m.recipe_id == "occupancy_light"]
        self.assertEqual(len(occ), 1)
        self.assertEqual(occ[0].area_id, "living")
        self.assertIn("binary_sensor.living_motion", occ[0].trigger_entity_ids)
        self.assertIn("light.living_lamp", occ[0].action_entity_ids)

    def test_occupancy_light_different_area_skipped(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion", area_id="living"),
            _snap("light.bedroom_lamp", area_id="bedroom", area_name="Bedroom"),
        ]
        matches = match_recipes(self.recipes, inventory)
        self.assertFalse(any(m.recipe_id == "occupancy_light" for m in matches))


class SafetyTests(unittest.TestCase):
    def test_lock_domain_is_blocked(self) -> None:
        self.assertIn("lock", BLOCKED_ACTION_DOMAINS)
        self.assertTrue(is_blocked(["lock.front_door"]))

    def test_light_is_allowed(self) -> None:
        self.assertFalse(is_blocked(["light.living_lamp"]))


class CompilerTests(unittest.TestCase):
    def test_yaml_is_deterministic_not_llm(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion"),
            _snap("light.living_lamp"),
        ]
        match = match_recipes(load_recipes(), inventory)[0]
        auto = compile_suggestion(match, suggestion_id="abc12345", trial=True)
        self.assertTrue(auto["id"].startswith("advisor_"))
        self.assertEqual(auto["initial_state"], False)
        self.assertEqual(auto["trigger"][0]["entity_id"], ["binary_sensor.living_motion"])
        self.assertEqual(auto["action"][0]["action"], "light.turn_on")
        self.assertIn("abc12345", auto["description"])

    def test_one_shot_run_uses_same_action_as_yaml(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion"),
            _snap("light.living_lamp"),
        ]
        match = match_recipes(load_recipes(), inventory)[0]
        auto = compile_suggestion(match, suggestion_id="abc12345", trial=True)
        domain, service, data = action_to_service_call(auto)
        self.assertEqual(domain, "light")
        self.assertEqual(service, "turn_on")
        self.assertEqual(data["entity_id"], ["light.living_lamp"])


class ActionIdTests(unittest.TestCase):
    def test_parse_run_button(self) -> None:
        parsed = parse_action("AR_abc12345")
        self.assertEqual(parsed, (KIND_RUN, "abc12345"))

    def test_parse_ignores_other_notifications(self) -> None:
        self.assertIsNone(parse_action("ALARM"))


class RecommenderTests(unittest.TestCase):
    def test_skips_conflict_with_existing_automation(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion"),
            _snap("light.living_lamp"),
        ]
        suggestions = recommend(
            inventory,
            existing_entity_sets=[
                {"binary_sensor.living_motion", "light.living_lamp", "sun.sun"}
            ],
        )
        self.assertEqual(suggestions, [])

    def test_scan_without_history_returns_catalog_matches(self) -> None:
        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion"),
            _snap("light.living_lamp"),
        ]
        suggestions = recommend(inventory, existing_entity_sets=[])
        self.assertTrue(suggestions)
        self.assertEqual(suggestions[0]["source"], "catalog")
        self.assertEqual(suggestions[0]["status"], "pending")
        self.assertIn("automation", suggestions[0])
        self.assertFalse(suggestions[0]["automation"]["initial_state"])


class DismissCooldownTests(unittest.TestCase):
    def test_dismissed_blocks_within_three_days(self) -> None:
        now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
        suggestion = {
            "status": "dismissed",
            "dismissed_at": (now - timedelta(days=2)).isoformat(),
            "recipe_id": "occupancy_light",
            "area_id": "living",
            "entities": ["binary_sensor.living_motion", "light.living_lamp"],
        }
        self.assertTrue(blocks_resuggestion(suggestion, now=now))

    def test_dismissed_allows_after_three_days(self) -> None:
        now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
        suggestion = {
            "status": "dismissed",
            "dismissed_at": (now - timedelta(days=DISMISS_COOLDOWN_DAYS, seconds=1)).isoformat(),
            "recipe_id": "occupancy_light",
            "area_id": "living",
            "entities": ["binary_sensor.living_motion", "light.living_lamp"],
        }
        self.assertFalse(blocks_resuggestion(suggestion, now=now))

    def test_pending_still_blocks(self) -> None:
        suggestion = {
            "status": "pending",
            "recipe_id": "occupancy_light",
            "area_id": "living",
            "entities": ["binary_sensor.living_motion", "light.living_lamp"],
        }
        self.assertTrue(blocks_resuggestion(suggestion))


class ActorTests(unittest.TestCase):
    def test_human_ui_is_learnable(self) -> None:
        actor = classify_actor(
            entity_domain="light", user_id="abc", parent_id=None
        )
        self.assertEqual(actor, ACTOR_HUMAN)
        self.assertTrue(is_learnable(actor))

    def test_automation_child_not_learnable(self) -> None:
        actor = classify_actor(
            entity_domain="light", user_id=None, parent_id="parent"
        )
        self.assertEqual(actor, ACTOR_AUTOMATION)
        self.assertFalse(is_learnable(actor))


class PatternTests(unittest.TestCase):
    def test_discovers_a_then_b_habit(self) -> None:
        base = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc).timestamp()
        events = []
        for i in range(5):
            t0 = base + i * 86400
            events.append(
                StoredEvent(
                    ts=t0,
                    entity_id="switch.desk",
                    domain="switch",
                    old_state="off",
                    new_state="on",
                    actor=ACTOR_HUMAN,
                    area_id="office",
                    hour=20,
                    weekday=0,
                )
            )
            events.append(
                StoredEvent(
                    ts=t0 + 30,
                    entity_id="light.desk",
                    domain="light",
                    old_state="off",
                    new_state="on",
                    actor=ACTOR_HUMAN,
                    area_id="office",
                    hour=20,
                    weekday=0,
                )
            )
        patterns = discover_patterns(events, min_support=3)
        self.assertTrue(patterns)
        top = patterns[0]
        self.assertEqual(top.trigger_entity_id, "switch.desk")
        self.assertEqual(top.action_entity_id, "light.desk")
        auto = habit_to_automation(top, suggestion_id="hab12345", trial=True)
        self.assertFalse(auto["initial_state"])
        self.assertEqual(auto["action"][0]["action"], "light.turn_on")

    def test_habit_merged_into_recommend(self) -> None:
        from automation_advisor.pattern import HabitPattern

        inventory = [
            _snap("binary_sensor.living_motion", device_class="motion"),
            _snap("light.living_lamp"),
            _snap("switch.desk", area_id="office"),
            _snap("light.desk", area_id="office"),
        ]
        pattern = HabitPattern(
            trigger_entity_id="switch.desk",
            trigger_to="on",
            action_entity_id="light.desk",
            action_to="on",
            support=5,
            confidence=0.8,
            lift=2.0,
            title="switch then light",
            explanation="test habit",
        )
        suggestions = recommend(inventory, habit_patterns=[pattern])
        sources = {s["source"] for s in suggestions}
        self.assertIn("catalog", sources)
        self.assertIn("habit", sources)


class CommunityStubTests(unittest.TestCase):
    def test_stub_rates_enrich_explanation(self) -> None:
        rates = load_community_rates()
        text = enrich_explanation("기본 설명.", "occupancy_light", rates)
        self.assertIn("%", text)


class EventStoreTests(unittest.TestCase):
    def test_insert_and_fetch(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(Path(tmp) / "e.db")
            store.insert(
                entity_id="light.a",
                domain="light",
                old_state="off",
                new_state="on",
                actor=ACTOR_HUMAN,
                area_id="living",
            )
            self.assertEqual(store.count(), 1)
            rows = store.fetch_since(7)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].entity_id, "light.a")


class PackageTests(unittest.TestCase):
    def test_domain_and_no_homeassistant_import(self) -> None:
        self.assertEqual(DOMAIN, "automation_advisor")
        self.assertNotIn("homeassistant", sys.modules)


if __name__ == "__main__":
    unittest.main()
