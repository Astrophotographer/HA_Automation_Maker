# Dashboard Web Panel — Design

Date: 2026-08-25

## Goal

Home Assistant 사이드바 커스텀 패널 **Dashboard**에 기기 모니터링·자동화 관리·분석(로그/임계값/알림 재전송) UI를 넣는다. 기존 채널톡형 챗봇 FAB는 유지하고, `chat_www`의 대시보드 플레이스홀더를 실제 화면으로 교체한다.

## Approved UX (mockup B-v2)

- **브랜드:** `Dashboard` (헤더 좌측). “Automation Advisor” 문자열을 제품명으로 쓰지 않는다.
- **헤더:** 동기화 시각(상대 시간) · 온라인 칩 · 연결된 기기 수.
- **상단 탭 3개**
  1. **기기** — 방(area)별 카드 그리드. 상태(on/off/이상) · 연결된 자동화/추천 수.
  2. **자동화** — 활성/추천 목록. 수정·삭제·승인/나중에/기각. **거절한 자동화 보기** 토글.
  3. **분석** — 서브탭 3개:
     - **로그** — 터미널 스타일 live-tail (줄번호 · 타임스탬프 · entity/state 컬러). 호버 시 스크롤 일시정지.
     - **임계값** — 추천 근거(support/confidence 등)와 임계 대비 바.
     - **알림 재전송** — 대기 추천별 「다시 보내기」. 성공 시 **우측 하단 토스트** (“알림 발송 완료”).
- **시각 구분:** 기기 = 파란 액센트, 자동화/추천 = 앰버 액센트.
- **한국어 UI.**

## Out of scope

- Lovelace `web_dashboard.py` inbox 제거/대체 (당분간 병행 가능).
- 기기 카드에서 직접 제어(켜기/끄기) — 조회·네비게이션만.
- 자동화 YAML 인라인 에디터 풀스크린 — 1차에서는 기존 서비스/챗 확인 플로우에 위임하거나 간단 모달 수준.
- 로그 WebSocket 실시간 푸시 — 1차는 폴링(예: 5–10초)으로 충분.
- 모바일 전용 레이아웃 재설계 (반응형은 기본 그리드만).

## Architecture

```
HA sidebar panel (panel_custom, path: dashboard)
  └─ panel.js → iframe → chat_www/index.html (+ dashboard.js)
        │
        ├─ GET  /api/automation_advisor/dashboard/summary   devices, sync, counts
        ├─ GET  /api/automation_advisor/dashboard/automations
        ├─ GET  /api/automation_advisor/dashboard/logs
        ├─ GET  /api/automation_advisor/dashboard/reasons
        ├─ POST /api/automation_advisor/dashboard/action    approve/later/dismiss/delete/resend/scan
        └─ (기존) /api/automation_advisor/chat*             FAB 챗봇 유지
```

- 정적 파일: 기존 `/api/automation_advisor/static/*` (`chat_www/`).
- 인증: iframe이 HA access token을 쿼리로 받아 API `Authorization: Bearer` (챗과 동일).
- 데이터 소스: `AdvisorCoordinator` (suggestions, event_store, habit_stats) + `hass.states` + area/device registry (`inventory`).

## Data model (API shapes)

### Summary

```json
{
  "synced_at": "ISO-8601",
  "device_count": 24,
  "anomaly_count": 2,
  "pending_count": 3,
  "devices": [
    {
      "entity_id": "light.living_room",
      "name": "거실 조명",
      "area": "거실",
      "state": "on",
      "ok": true,
      "automation_count": 2,
      "suggestion_count": 1
    }
  ]
}
```

`ok: false` 또는 알 수 없는/unavailable 상태는 이상(warn) 칩.

### Automations

Suggestions with status in `{pending, previewed, deployed, dismissed}` plus deployed automation aliases. Toggle `include_dismissed` query flag.

Actions mapped to coordinator:
| UI | Backend |
|---|---|
| 승인 / 실행 | `async_run_once` 또는 `async_deploy` (status에 따라) |
| 나중에 | `async_later` |
| 기각 | `async_dismiss` |
| 삭제 | `async_delete` |
| 수정 | 1차 미구현 — 버튼은 챗 FAB 안내 토스트만 (“수정은 챗봇에서”) |
| 다시 보내기 | 기존 push/notification 경로로 해당 suggestion 재프롬프트 |
| 스캔 | `async_scan` + `async_prompt_new` |

### Logs

EventStore recent rows → terminal lines: sequential `n`, `ts`, `entity_id`, `old→new`, `actor`.

### Reasons / thresholds

Habit/catalog suggestion explanation + numeric score when present (`confidence` / support). Global thresholds from `const.py` (`MIN_PATTERN_CONFIDENCE`, `MIN_PATTERN_SUPPORT`, …) exposed as labels so UI can show “임계 0.75”.

## Panel / copy rules

- Sidebar title: **Dashboard** (`PANEL_TITLE`을 Advisor → Dashboard로 변경).
- Page `<title>`: `Dashboard`.
- 챗봇 FAB·채팅 패드 동작은 변경하지 않는다. 대시보드 본문만 플레이스홀더/veil을 제거해 교체.

## Error handling

- 401: “HA에 로그인한 상태로 패널을 열어주세요.”
- API/ coordinator 오류: 토스트 또는 인라인 배너, HA 크래시 없음.
- 재전송 실패: 토스트에 실패 메시지 (성공과 동일 위치).

## Testing

- Python: dashboard view handlers — summary grouping by area, action routing, dismissed filter.
- Frontend: 수동 확인 체크리스트 (탭 전환, 거절 토글, 터미널 로그 렌더, 재전송 토스트).
- 기존 chat API 회귀: FAB 메시지 송수신 유지.

## Implementation notes

- Prefer new modules `dashboard_http.py` + `chat_www/dashboard.js` (or split CSS) rather than bloating `chat_http.py` / monolithic `index.html` further; wire registration from existing `async_setup_chat` (or rename to panel setup).
- Keep visual language close to approved mockup (dark shell, blue/amber accents, mono terminal for logs).
- Cache-bust `panel.js` / static assets via query `v=` bump when shipping UI.
