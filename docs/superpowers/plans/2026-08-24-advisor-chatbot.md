# Advisor Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve an Advisor iframe page with a Channel Talk-style chat widget that talks to Spark vLLM through HA, with confirm-gated automation writes.

**Architecture:** Static HTML/JS on HA HTTP; POST chat/confirm views; in-process tool agent; confirmed YAML goes through AdvisorCoordinator into `automation_advisor.yaml`.

**Tech Stack:** Home Assistant custom integration (Python 3.12), urllib OpenAI-compatible client, vanilla JS widget, unittest.

## Global Constraints

- Browser never calls Spark or holds `llm_api_key`.
- Writes require confirm token; blocked action domains never register.
- Dashboard slot is placeholder only.
- Do not commit unless the user asks.

## File map

- Create: `custom_components/automation_advisor/chat_yaml.py`
- Create: `custom_components/automation_advisor/chat_llm.py`
- Create: `custom_components/automation_advisor/chat_pending.py`
- Create: `custom_components/automation_advisor/chat_agent.py`
- Create: `custom_components/automation_advisor/chat_http.py`
- Create: `custom_components/automation_advisor/chat_www/index.html`
- Create: `tests/test_chat.py`
- Modify: `coordinator.py`, `integration.py`, `const.py`, `manifest.json`

### Task 1: YAML + pending + fallback parser tests

- [x] Implemented in `tests/test_chat.py` and the modules above.

### Task 2: Agent + HTTP + widget

- [x] Chat views, iframe panel, Channel Talk FAB, Spark client, coordinator chat CRUD.

### Task 3: Wire integration

- [x] `async_setup_entry` registers chat HTTP once; version bump 0.2.18.
