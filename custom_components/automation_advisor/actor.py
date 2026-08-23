"""Actor attribution — automation/token runs are not learned as habits."""

from __future__ import annotations

# Controllable domains that may come from a physical switch without user_id.
PHYSICAL_DOMAINS = frozenset(
    {"light", "switch", "fan", "cover", "input_boolean", "media_player", "climate"}
)
# Value-only domains: context at most, never habit actions.
SENSOR_DOMAINS = frozenset(
    {"binary_sensor", "sensor", "sun", "person", "device_tracker", "weather", "zone"}
)

ACTOR_HUMAN = "human_ui"
ACTOR_PHYSICAL = "physical"
ACTOR_AUTOMATION = "automation"
ACTOR_ADVISOR = "advisor"
ACTOR_SENSOR = "sensor"
ACTOR_UNKNOWN = "unknown"

LEARNABLE = frozenset({ACTOR_HUMAN, ACTOR_PHYSICAL})


def classify_actor(
    *,
    entity_domain: str,
    user_id: str | None,
    parent_id: str | None,
    context_id: str | None = None,
    advisor_context_ids: set[str] | None = None,
) -> str:
    """Classify who caused a state change.

    Manual UI: user_id present, no parent.
    Physical: no user_id/parent, controllable domain.
    Automation/script child: parent_id set.
    Advisor: context id recorded from our one-shot / deployed runs.
    Sensor: passive domains.
    """
    if advisor_context_ids and context_id and context_id in advisor_context_ids:
        return ACTOR_ADVISOR

    if parent_id:
        return ACTOR_AUTOMATION

    if user_id:
        return ACTOR_HUMAN

    if entity_domain in SENSOR_DOMAINS:
        return ACTOR_SENSOR

    if entity_domain in PHYSICAL_DOMAINS:
        return ACTOR_PHYSICAL

    return ACTOR_UNKNOWN


def is_learnable(actor: str) -> bool:
    return actor in LEARNABLE
