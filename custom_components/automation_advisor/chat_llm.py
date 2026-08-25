"""OpenAI-compatible chat completions for the Advisor chatbot (Spark vLLM)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from .const import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL

_LOGGER = logging.getLogger(__name__)


def resolve_llm_endpoint(
    base_url: str | None, model: str | None, api_key: str | None
) -> tuple[str, str, str] | None:
    base = (base_url or "").strip().rstrip("/")
    key = (api_key or "").strip()
    mdl = (model or "").strip()
    if not base and not key:
        return None
    if not base:
        base = DEFAULT_OPENAI_BASE_URL
        mdl = mdl or DEFAULT_OPENAI_MODEL
    if not mdl:
        return None
    return base, mdl, key or "EMPTY"


def llm_origin(base_url: str) -> str:
    """http://host:8000/v1 → http://host:8000 (for /health)."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def _http_get_json(
    url: str, *, api_key: str | None = None, timeout: float = 5.0
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        code = getattr(resp, "status", 200)
        try:
            return int(code), json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return int(code), {}


def _host_from_origin(origin: str) -> str | None:
    """http://172.30.1.53:8000 → 172.30.1.53"""
    try:
        # urlparse needs a scheme
        from urllib.parse import urlparse

        parsed = urlparse(origin if "://" in origin else f"http://{origin}")
        return parsed.hostname
    except Exception:  # noqa: BLE001
        return None


def _probe_temp_payload(payload: Any) -> int | float | None:
    if not isinstance(payload, dict):
        return None
    if "temp_c" in payload and isinstance(payload["temp_c"], (int, float)):
        return payload["temp_c"]
    # Some sidecars nest GPU stats
    gpu = payload.get("gpu")
    if isinstance(gpu, dict) and isinstance(gpu.get("temp_c"), (int, float)):
        return gpu["temp_c"]
    return None


def probe_llm_status(
    *,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Check Spark connectivity + GPU temp from bot /health (temp_c)."""
    endpoint = resolve_llm_endpoint(base_url, model, api_key)
    if not endpoint:
        return {
            "configured": False,
            "ok": False,
            "temp_c": None,
            "detail": "llm_not_configured",
        }

    llm_base, _mdl, llm_key = endpoint
    origin = llm_origin(llm_base)
    temp_c: int | float | None = None
    ok = False
    detail = "unreachable"

    # 1) Same-origin /health (vLLM rarely has temp_c)
    try:
        code, payload = _http_get_json(
            f"{origin}/health", api_key=llm_key, timeout=timeout
        )
        if code == 200:
            temp_c = _probe_temp_payload(payload)
            if isinstance(payload, dict) and payload.get("ok") is False:
                ok = False
                detail = "health_not_ok"
            else:
                ok = True
                detail = "health"
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("LLM /health probe failed: %s", err)

    # 2) Spark bot sidecar on :8080 — {ok, temp_c} (room.deungchon.org style)
    if temp_c is None:
        host = _host_from_origin(origin)
        if host:
            for port in (8080, 8081):
                try:
                    code, payload = _http_get_json(
                        f"http://{host}:{port}/health",
                        api_key=None,
                        timeout=timeout,
                    )
                    if code == 200:
                        temp_c = _probe_temp_payload(payload)
                        if temp_c is not None:
                            detail = f"health_{port}"
                            if not ok and (
                                not isinstance(payload, dict)
                                or payload.get("ok") is not False
                            ):
                                ok = True
                            break
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("LLM :%s /health probe failed: %s", port, err)

    if not ok:
        try:
            code, _payload = _http_get_json(
                f"{llm_base}/models", api_key=llm_key, timeout=timeout
            )
            if code == 200:
                ok = True
                detail = "models"
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("LLM /models probe failed: %s", err)
            detail = str(err)[:120]

    return {
        "configured": True,
        "ok": ok,
        "temp_c": temp_c,
        "detail": detail,
        "origin": origin,
    }


def chat_completions(
    *,
    base_url: str,
    model: str,
    api_key: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Return the assistant message object from chat/completions."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"LLM HTTP {err.code}: {detail}") from err
    except Exception as err:  # noqa: BLE001
        raise RuntimeError(f"LLM 요청 실패: {err}") from err

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("LLM 응답에 choices가 없습니다.")
    message = choices[0].get("message") or {}
    if not isinstance(message, dict):
        raise RuntimeError("LLM message 형식이 올바르지 않습니다.")
    return message
