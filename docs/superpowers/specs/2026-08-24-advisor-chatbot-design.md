# Advisor Chatbot (Channel Talk widget) — Design

Date: 2026-08-24

## Goal

Home Assistant 커스텀 페이지에서 대시보드는 전체 화면(내용은 이후), 오른쪽 아래 채널톡형 아이콘으로 Spark vLLM 챗봇을 여닫는다. 챗봇은 추천·자동화 목록, 장비 상태, 로그를 조회하고, 자동화를 YAML로 만들거나 수정·삭제할 수 있다. 쓰기는 확인 버튼 후에만 HA에 반영한다.

## Out of scope (this slice)

- 왼쪽/전체 대시보드 위젯 구성 (플레이스홀더만)
- Lovelace inbox 대체
- LLM이 카탈로그 컴파일러를 우회해 잠금/알람 등 차단 도메인 액션을 등록하는 것
- 브라우저가 Spark를 직접 호출하는 것

## UX

- 사이드바 iframe 패널: `automation-advisor-ui` (제목: Advisor)
- 레이아웃: HA 스타일 셸 + 대시보드 슬롯(가림막) + 우하단 FAB
- FAB 토글: 채팅 패드 열림/닫힘. 패드 × 또는 FAB 재클릭으로 닫힘
- 조회 답변은 말풍선. 추가/수정/삭제는 YAML 요약 + **등록/적용/삭제** / **취소**
- 한국어 UI

## Architecture

```
Browser (same-origin) → HA views
  GET  /api/automation_advisor/static/*   HTML/CSS/JS
  POST /api/automation_advisor/chat       {session_id, message}
  POST /api/automation_advisor/chat/confirm  {token, accept}
HA Python agent → Spark OpenAI-compatible POST {llm_base_url}/chat/completions
Tools run in-process against AdvisorCoordinator + hass.states + EventStore
Confirmed writes → suggestion list (source=chat) → automation_advisor.yaml + automation.reload
```

LLM URL/model/key: existing config entry `llm_base_url`, `llm_model`, `llm_api_key`. Keys never go to the browser.

## Agent

- System prompt: Korean assistant; use tools; never claim a write succeeded until the user confirms in UI.
- OpenAI `tools` function calling. If the model returns no `tool_calls`, parse JSON / fenced `tool` blocks as fallback.
- Read tools execute immediately. Write tools only build a **pending write** (token, kind, yaml, summary). HTTP response includes `pending` for the widget buttons.
- Confirm accept: validate YAML again, `is_blocked()` on action entity ids, then coordinator create/update/delete.
- Confirm reject: drop token.
- Tokens live in memory, expire after 15 minutes.
- Max 6 tool rounds per user message. LLM timeout 60s.

## Tools

| Tool | Effect |
|---|---|
| `list_suggestions` | pending/previewed/dismissed catalog+habit+chat suggestions |
| `list_automations` | deployed advisor automations (id, alias, status) |
| `get_states` | entity_id / area / text query against `hass.states` + display names |
| `get_logs` | `EventStore.fetch_recent` |
| `propose_create_automation` | pending create from YAML |
| `propose_update_automation` | pending update by suggestion id or automation id |
| `propose_delete_automation` | pending delete by id |

## YAML rules

- Must parse as a mapping with `trigger` (or `triggers`) and `action` (or `actions`).
- Chat automations get `id` `advisor_chat_<suggestion_id>` if missing.
- `initial_state: false` (trial) unless the YAML explicitly sets it.
- Action entity domains in `safety.BLOCKED_ACTION_DOMAINS` are rejected.
- Stored as a suggestion `source: "chat"` so `_rewrite_automations_file` includes them.

## Errors

- LLM unset: tell the user to set Spark base URL / model in integration options.
- Spark failure: Korean error, no crash of HA.
- 401: widget tells user to open the panel while logged into HA.

## Testing

- Pure Python: YAML gate, blocked domains, pending token accept/reject, tool-call fallback parser.
- No live Spark in CI.
