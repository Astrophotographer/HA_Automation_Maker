"""Config flow — trial mode + v2 habit / stub / optional OpenAI-compatible LLM."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_COMMUNITY_STUB,
    CONF_HABIT_LEARNING,
    CONF_LLM_API_KEY,
    CONF_LLM_BASE_URL,
    CONF_LLM_MODEL,
    CONF_MIN_OBSERVE_DAYS,
    CONF_TRIAL_MODE,
    DEFAULT_COMMUNITY_STUB,
    DEFAULT_HABIT_LEARNING,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_MIN_OBSERVE_DAYS,
    DEFAULT_TRIAL_MODE,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TRIAL_MODE, default=DEFAULT_TRIAL_MODE): bool,
        vol.Required(CONF_HABIT_LEARNING, default=DEFAULT_HABIT_LEARNING): bool,
        vol.Required(CONF_MIN_OBSERVE_DAYS, default=DEFAULT_MIN_OBSERVE_DAYS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
        vol.Required(CONF_COMMUNITY_STUB, default=DEFAULT_COMMUNITY_STUB): bool,
        vol.Optional(CONF_LLM_BASE_URL, default=DEFAULT_LLM_BASE_URL): str,
        vol.Optional(CONF_LLM_MODEL, default=DEFAULT_LLM_MODEL): str,
        vol.Optional(CONF_LLM_API_KEY, default=""): str,
    }
)


class AutomationAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Automation Advisor", data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AutomationAdvisorOptionsFlow()


class AutomationAdvisorOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        data = self.config_entry.data
        opts = self.config_entry.options

        def _get(key, default):
            return opts.get(key, data.get(key, default))

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRIAL_MODE, default=_get(CONF_TRIAL_MODE, DEFAULT_TRIAL_MODE)
                ): bool,
                vol.Required(
                    CONF_HABIT_LEARNING,
                    default=_get(CONF_HABIT_LEARNING, DEFAULT_HABIT_LEARNING),
                ): bool,
                vol.Required(
                    CONF_MIN_OBSERVE_DAYS,
                    default=_get(CONF_MIN_OBSERVE_DAYS, DEFAULT_MIN_OBSERVE_DAYS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
                vol.Required(
                    CONF_COMMUNITY_STUB,
                    default=_get(CONF_COMMUNITY_STUB, DEFAULT_COMMUNITY_STUB),
                ): bool,
                vol.Optional(
                    CONF_LLM_BASE_URL,
                    default=_get(CONF_LLM_BASE_URL, DEFAULT_LLM_BASE_URL),
                ): str,
                vol.Optional(
                    CONF_LLM_MODEL, default=_get(CONF_LLM_MODEL, DEFAULT_LLM_MODEL)
                ): str,
                vol.Optional(
                    CONF_LLM_API_KEY, default=_get(CONF_LLM_API_KEY, "")
                ): str,
            }
        )

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=schema)
