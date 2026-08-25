# Dashboard Web Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `chat_www` dashboard placeholder with a working Dashboard UI (기기 / 자동화 / 분석) backed by HA REST APIs, keeping the chat FAB.

**Architecture:** Pure Python builders in `dashboard_api.py` assemble JSON from `AdvisorCoordinator` + inventory/states. `dashboard_http.py` registers authenticated views. Frontend `dashboard.js` mounts into `#dash-root` in `index.html` and polls/actions via Bearer token (same as chat).

**Tech Stack:** Home Assistant custom integration (Python 3.12), aiohttp views, vanilla JS, unittest.

## Global Constraints

- Brand string in UI header/title/sidebar: **Dashboard** (not “Automation Advisor”).
- Korean UI copy.
- Device accent blue / automation accent amber; logs are terminal-style.
- Chat FAB behavior unchanged.
- Do not remove Lovelace `web_dashboard.py` in this plan.
- 1차: 자동화 **수정** = toast “수정은 챗봇에서” only.
- Resend uses existing `ask_run_once` / `async_reprompt` notification path.
- Do not commit unless the user asks.

## File map

- Create: `custom_components/automation_advisor/dashboard_api.py` — pure builders + action dispatch helpers
- Create: `custom_components/automation_advisor/dashboard_http.py` — HA HTTP views + setup hook
- Create: `custom_components/automation_advisor/chat_www/dashboard.js` — UI
- Create: `tests/test_dashboard.py`
- Modify: `custom_components/automation_advisor/chat_http.py` — call dashboard setup; `PANEL_TITLE = "Dashboard"`; bump `module_url` `v=`
- Modify: `custom_components/automation_advisor/chat_www/index.html` — replace veil/placeholder with `#dash-root` + script tag; keep widget
- Modify: `custom_components/automation_advisor/chat_www/panel.js` — iframe title Dashboard (optional)
- Modify: `custom_components/automation_advisor/const.py` — version bump
- Modify: `custom_components/automation_advisor/manifest.json` — version bump

---

### Task 1: Dashboard builders + unit tests

**Files:**
- Create: `custom_components/automation_advisor/dashboard_api.py`
- Create: `tests/test_dashboard.py`

**Interfaces:**
- Produces:
  - `build_summary(*, synced_at: str, devices: list[dict], pending_count: int) -> dict`
  - `build_device_row(entity_id, name, area, state, automation_count, suggestion_count) -> dict` with `ok: bool`
  - `list_automations(suggestions: list[dict], *, include_dismissed: bool) -> list[dict]`
  - `build_log_lines(events: list, *, names: dict[str,str], start_n: int = 1) -> list[dict]`
  - `build_reasons(suggestions: list[dict], *, min_confidence: float, min_support: int) -> dict` with `thresholds` + `items`
  - `normalize_action(kind: str) -> str` raising `ValueError` on unknown

- [x] **Step 1: Write failing tests**
- [x] **Step 2: Run tests — expect FAIL (module missing)**
- [x] **Step 3: Implement `dashboard_api.py`**
- [x] **Step 4: Run tests — expect PASS**

```python
# tests/test_dashboard.py
from automation_advisor.dashboard_api import (
    build_device_row,
    build_log_lines,
    build_reasons,
    build_summary,
    list_automations,
    normalize_action,
)

def test_device_ok_false_when_unavailable():
    row = build_device_row("light.x", "X", "거실", "unavailable", 0, 0)
    assert row["ok"] is False
    assert row["area"] == "거실"

def test_summary_counts():
    s = build_summary(
        synced_at="2026-08-25T00:00:00+00:00",
        devices=[
            build_device_row("light.a", "A", "거실", "on", 1, 0),
            build_device_row("light.b", "B", "침실", "unavailable", 0, 1),
        ],
        pending_count=2,
    )
    assert s["device_count"] == 2
    assert s["anomaly_count"] == 1
    assert s["pending_count"] == 2

def test_list_automations_hides_dismissed_by_default():
    sug = [
        {"id": "1", "title": "A", "status": "pending", "source": "habit"},
        {"id": "2", "title": "B", "status": "dismissed", "source": "habit"},
        {"id": "3", "title": "C", "status": "deployed", "source": "catalog",
         "automation": {"id": "auto_c", "alias": "C"}},
    ]
    out = list_automations(sug, include_dismissed=False)
    assert [x["id"] for x in out] == ["1", "3"]
    out2 = list_automations(sug, include_dismissed=True)
    assert [x["id"] for x in out2] == ["1", "2", "3"]

def test_log_lines_numbering():
    class Ev:
        def __init__(self):
            self.ts = 1700000000.0
            self.entity_id = "light.a"
            self.old_state = "off"
            self.new_state = "on"
            self.actor = "human_ui"
    lines = build_log_lines([Ev()], names={"light.a": "거실등"}, start_n=100)
    assert lines[0]["n"] == 100
    assert lines[0]["entity_id"] == "light.a"
    assert "on" in lines[0]["msg"]

def test_reasons_thresholds():
    r = build_reasons(
        [{"id": "1", "title": "T", "status": "pending", "source": "habit",
          "confidence": 0.82, "support": 5, "explanation": "반복"}],
        min_confidence=0.75,
        min_support=3,
    )
    assert r["thresholds"]["min_confidence"] == 0.75
    assert r["items"][0]["score"] == 0.82
    assert r["items"][0]["above_threshold"] is True

def test_normalize_action():
    assert normalize_action("approve") == "approve"
    assert normalize_action("resend") == "resend"
    try:
        normalize_action("nope")
        assert False
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
cd /Users/chris/Desktop/Develop/hackerton/HA_Automation_Maker
python -m pytest tests/test_dashboard.py -v
```

- [ ] **Step 3: Implement `dashboard_api.py`**

Implement the functions above. `ok` is False when `state` in `{unavailable, unknown, none, ""}` (casefold).  
`list_automations` fields per item: `id`, `title`, `status`, `source`, `explanation` (≤240), `automation_id`, `alias`, `score` (optional).  
`build_log_lines` `msg` like `name entity_id old→new actor=…`.  
`normalize_action` allows: `approve`, `deploy`, `later`, `dismiss`, `delete`, `resend`, `resend_all`, `scan`.

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_dashboard.py -v
```

---

### Task 2: HTTP views + wire-up

**Files:**
- Create: `custom_components/automation_advisor/dashboard_http.py`
- Modify: `custom_components/automation_advisor/chat_http.py` — `PANEL_TITLE = "Dashboard"`; after chat views registered, call `await async_setup_dashboard(hass, coordinator)`; bump panel `v=` to match `const.VERSION`

**Interfaces:**
- Consumes: builders from Task 1; `coordinator` methods `async_run_once`, `async_deploy`, `async_later`, `async_dismiss`, `async_delete`, `async_scan`, `async_prompt_new`, `async_reprompt`, `pending_suggestions`, `previewed_suggestions`, `suggestions`, `event_store`, `habit_stats`
- Consumes: `inventory.build_entity_display_names`, `notifications.ask_run_once`
- Produces: routes under `/api/automation_advisor/dashboard/*` with `requires_auth = True`

- [ ] **Step 1: Implement views**

```
GET  /api/automation_advisor/dashboard/summary
GET  /api/automation_advisor/dashboard/automations?include_dismissed=0|1
GET  /api/automation_advisor/dashboard/logs?limit=80
GET  /api/automation_advisor/dashboard/reasons
POST /api/automation_advisor/dashboard/action
     body: {"kind": "...", "suggestion_id": "..."}
```

Summary assembly:
- Iterate controllable-ish domains: `light`, `switch`, `climate`, `cover`, `fan`, `media_player`, `binary_sensor`, `lock` (skip `OBSERVE_SKIP_DOMAINS`).
- Area from registry via same pattern as `inventory` (entity → device → area name); fallback `"기타"`.
- Count automations/suggestions whose automation `entity_id` list or trigger entities intersect device entity_id (best-effort: scan suggestion `automation` YAML-ish dict + `entities` field if present).
- `synced_at`: `datetime.now(timezone.utc).isoformat()`.

Action routing:
| kind | call |
|---|---|
| approve | if pending → `async_run_once`; if previewed → `async_deploy` |
| deploy | `async_deploy` |
| later | `async_later` |
| dismiss | `async_dismiss` |
| delete | `async_delete` |
| resend | `ask_run_once` for that id; set `asked_run=True`; save if available |
| resend_all | `async_reprompt(limit=10)` |
| scan | `async_scan` then `async_prompt_new` |

Return JSON `{"ok": true, ...}` or `{"ok": false, "error": "..."}` with HTTP 400 on bad kind.

- [ ] **Step 2: Register from `async_setup_chat`** (or call from `integration.py` right after chat setup — prefer one call inside `async_setup_chat` end to keep panel lifecycle together).

- [ ] **Step 3: Smoke-import test**

```bash
python -c "from automation_advisor.dashboard_http import async_setup_dashboard; print('ok')"
```

(from `custom_components` on `sys.path`)

---

### Task 3: Frontend Dashboard UI

**Files:**
- Create: `custom_components/automation_advisor/chat_www/dashboard.js`
- Modify: `custom_components/automation_advisor/chat_www/index.html`

**Interfaces:**
- Consumes: APIs from Task 2; URL query `access_token` (existing panel.js injection)
- Produces: mounted UI in `#dash-root`; global `window.AdvisorDashboard.start()`

- [ ] **Step 1: Replace stage placeholder in `index.html`**

Remove `.veil` / placeholder grid content. Structure:

```html
<div class="stage" id="dash-root">
  <!-- filled by dashboard.js -->
</div>
<!-- existing .widget FAB unchanged -->
<script src="./dashboard.js"></script>
<script>
  // after chat boot, also:
  if (window.AdvisorDashboard) AdvisorDashboard.start();
</script>
```

Keep existing chat widget CSS/JS. Set `<title>Dashboard</title>`. Header brand text inside dashboard.js: `Dashboard`.

- [ ] **Step 2: Implement `dashboard.js`**

Tabs: 기기 | 자동화 | 분석. Analysis subtabs: 로그 | 임계값 | 알림 재전송.  
Fetch helpers with `Authorization: Bearer ${token}`.  
Poll summary + logs every 8s while Analysis/로그 visible (or always poll summary every 15s).  
Reject toggle filters client via `include_dismissed`.  
Resend / resend_all / scan → POST action → toast bottom-right “알림 발송 완료” or error.  
Edit button → toast “수정은 챗봇에서 진행해 주세요.”  
Terminal log: monospace lines with `n`, `ts`, `msg`; CSS scroll animation optional; pause on hover.  
Relative sync time (“방금 전”, “N분 전”).

- [ ] **Step 3: Manual checklist** (on HA): open sidebar Dashboard → three tabs → toggle dismissed → resend toast → chat FAB still opens.

---

### Task 4: Version / panel chrome

**Files:**
- Modify: `const.py` VERSION (e.g. `0.2.27`)
- Modify: `manifest.json` version match
- Modify: `chat_http.py` `module_url` / config version match
- Modify: `panel.js` iframe `title="Dashboard"`

- [ ] **Step 1: Bump versions consistently**
- [ ] **Step 2: Run full related tests**

```bash
python -m pytest tests/test_dashboard.py tests/test_chat.py -v
```

Expected: all PASS.

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| Brand Dashboard | 3, 4 |
| Header sync + device count | 1, 2, 3 |
| Tab 기기 | 1–3 |
| Tab 자동화 + reject toggle | 1–3 |
| Analysis subtabs logs/threshold/resend | 1–3 |
| Terminal logs | 1, 3 |
| Resend toast | 3 |
| Chat FAB unchanged | 3 |
| REST API paths | 2 |
| Edit → chat toast | 3 |
| Unit tests builders | 1 |

## Execution

User asked to proceed: **Inline Execution** in this session (executing-plans style), task-by-task with verification.
