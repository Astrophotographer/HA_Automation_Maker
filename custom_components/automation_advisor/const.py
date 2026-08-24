"""Constants for Automation Advisor."""

DOMAIN = "automation_advisor"
VERSION = "0.2.15"

CONF_TRIAL_MODE = "trial_mode"
CONF_HABIT_LEARNING = "habit_learning"
CONF_MIN_OBSERVE_DAYS = "min_observe_days"
CONF_LLM_BASE_URL = "llm_base_url"
CONF_LLM_MODEL = "llm_model"
CONF_LLM_API_KEY = "llm_api_key"
CONF_COMMUNITY_STUB = "community_stub"

DEFAULT_TRIAL_MODE = True
DEFAULT_HABIT_LEARNING = True
DEFAULT_MIN_OBSERVE_DAYS = 3
DEFAULT_COMMUNITY_STUB = True
# OpenAI-compatible endpoint (vLLM on Spark). Empty = LLM off unless api_key set (OpenAI cloud).
DEFAULT_LLM_BASE_URL = ""
DEFAULT_LLM_MODEL = ""
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

# After dismiss, the same recipe+area+entities may be suggested again.
DISMISS_COOLDOWN_DAYS = 3

# Habit pattern thresholds (v2).
PATTERN_WINDOW_SECONDS = 120
MIN_PATTERN_SUPPORT = 3
MIN_PATTERN_CONFIDENCE = 0.5
MIN_PATTERN_LIFT = 1.2
EVENT_RETENTION_DAYS = 30

# Domains ignored by habit observer and recorder backfill.
OBSERVE_SKIP_DOMAINS = frozenset(
    {
        "automation",
        "script",
        "scene",
        "zone",
        "persistent_notification",
        "conversation",
        "update",
        "button",
        "event",
        "todo",
        "calendar",
        "camera",
        "image",
        "tts",
        "stt",
        "assist_satellite",
    }
)

SUGGESTIONS_FILENAME = ".automation_advisor_suggestions.json"
AUTOMATIONS_FILENAME = "automation_advisor.yaml"
EVENT_DB_FILENAME = ".automation_advisor_events.db"
