"""Optional LLM explanation for verified patterns. Never invents YAML.

Talks to any OpenAI-compatible chat API (cloud OpenAI or local vLLM on Spark).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .const import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL

_LOGGER = logging.getLogger(__name__)


def explain_pattern(
    *,
    title: str,
    facts: str,
    fallback: str,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """Return a short Korean explanation. Falls back if unset or request fails."""
    base = (base_url or "").strip().rstrip("/")
    key = (api_key or "").strip()
    mdl = (model or "").strip()

    if not base and not key:
        return fallback

    if not base:
        base = DEFAULT_OPENAI_BASE_URL
        mdl = mdl or DEFAULT_OPENAI_MODEL
    elif not mdl:
        # vLLM often serves one model; empty name fails — caller should set it.
        _LOGGER.warning("LLM model empty with base_url=%s; using fallback", base)
        return fallback

    try:
        return (
            _chat_explain(
                base_url=base,
                model=mdl,
                api_key=key or "EMPTY",
                title=title,
                facts=facts,
            )
            or fallback
        )
    except Exception as err:  # noqa: BLE001 — never break scan on LLM
        _LOGGER.warning("LLM explain failed: %s", err)
        return fallback


def _chat_explain(
    *,
    base_url: str,
    model: str,
    api_key: str,
    title: str,
    facts: str,
) -> str | None:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain an already-verified Home Assistant habit pattern "
                    "in one or two short Korean sentences. Do not invent YAML or new automations."
                ),
            },
            {
                "role": "user",
                "content": f"제목: {title}\n근거: {facts}\n짧은 설명만 쓰세요.",
            },
        ],
        "max_tokens": 120,
        "temperature": 0.3,
    }
    url = f"{base_url}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content")
        or payload.get("choices", [{}])[0]
        .get("message", {})
        .get("reasoning")
        or ""
    ).strip()
    return text or None
