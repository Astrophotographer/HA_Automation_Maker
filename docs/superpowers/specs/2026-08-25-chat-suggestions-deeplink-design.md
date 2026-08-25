# Chat → Suggestions List Deep Link — Design

Date: 2026-08-25

## Goal

사용자가 챗봇에 「추천 목록/리스트 보여줘」라고 하면, 채팅에 긴 표·카드 목록을 그리지 않는다.  
짧은 요약 + **목록 보기** 버튼만 보여 주고, 클릭 시 Advisor 패널 메인(대시보드)의 추천 리스트로 이동한다.

관련: [Dashboard Web Panel design](./2026-08-25-dashboard-web-panel-design.md) — 메인의 「자동화/추천」 영역과 맞춘다. 대시보드 전체가 아직 없으면 **추천 리스트 뷰만** 먼저 채워도 된다.

## Approved decisions

| 항목 | 선택 |
|------|------|
| 목록 표시 위치 | Advisor 패널 메인 (챗 버블 안 X) |
| 채팅 응답 | 짧은 한 줄 요약 + **목록 보기** 버튼 |
| 요약 예 | `미리보기 2 · 배포됨 3 · 기각 3` |
| 버튼 클릭 | 챗봇 닫기 → 메인 추천 리스트 표시 |
| 리스트 액션 | 미리보기만 **적용 / 기각**. 수정은 채팅. 배포됨·기각은 읽기 전용 |
| 구현 방식 | 구조화 `ui` 페이로드 (URL 딥링크·텍스트만 링크 아님) |

## Out of scope

- 채팅 안에 추천 카드/마크다운 표 렌더링
- Lovelace `web_dashboard.py` inbox 대체
- 리스트에서 YAML 수정·삭제 풀 UI (적용 확인은 기존 chat confirm / coordinator 서비스 재사용)
- 대시보드 기기·분석 탭 전체 (별도 스펙)

## User flow

```
사용자: "추천리스트 보여줘"
    → Agent: list_suggestions (또는 counts만)
    → HTTP 응답:
         reply: "미리보기 2 · 배포됨 3 · 기각 3"
         ui: { "action": "open_suggestions", "counts": { ... } }
    → 챗 UI: 버블 + [목록 보기] 버튼
    → 클릭: pad 닫기 → 메인에 추천 리스트 뷰
    → 미리보기 카드 [적용]/[기각] → coordinator deploy / dismiss
```

목록을 말로만 나열하지 않도록 시스템/툴 가이드: 「전체 목록 요청 시 표 대신 요약 + open_suggestions」.

## Chat UI

- `addBubble`은 기존처럼 `reply` 텍스트.
- `data.ui?.action === "open_suggestions"` 이면 같은 행(또는 바로 아래)에 **목록 보기** 버튼.
- 클릭 핸들러: `toggle(false)` 후 메인 스테이지를 suggestions 뷰로 전환 (`showSuggestionsView()`).
- 버튼이 없어도 `reply`만으로 동작은 깨지지 않음 (하위 호환).

## Main list UI (Advisor stage)

플레이스홀더(veil / “대시보드가 들어갑니다”)를 **추천 리스트 뷰**로 교체하거나, 대시보드 탭이 있으면 **자동화** 탭의 추천 섹션으로 포커스.

- 제목: 추천 (또는 대시보드 스펙의 「자동화」 탭)
- 상단 요약: 상태별 개수
- 그룹 순서: 대기(`pending`) · 미리보기(`previewed`) → 배포됨 → 기각  
  (대기·미리보기는 한 섹션으로 묶되 배지로 구분해도 됨)
- 카드: 제목 · 상태 배지 · 짧은 설명 · id(mono, 작게)
- `pending` / `previewed`: **적용** / **기각** (적용은 기존 coordinator 경로: run 또는 deploy)
- 배포됨·기각: 액션 없음
- 시각: 기존 `chat_www` 토큰(Instrument Sans, panel 색, HA 블루 / ok 그린)

목업: `.superpowers/brainstorm/mockups/advisor-suggestions-list.html`

## Data / API

### Chat response extension

기존:

```json
{ "reply": "...", "pending": null }
```

추가(옵션):

```json
{
  "reply": "미리보기 2 · 배포됨 3 · 기각 3",
  "pending": null,
  "ui": {
    "action": "open_suggestions",
    "counts": {
      "previewed": 2,
      "deployed": 3,
      "dismissed": 3,
      "pending": 0
    }
  }
}
```

- `ui`는 서버가 툴 결과·의도에서 채운다. LLM이 긴 표를 `reply`에 쓰더라도 UI는 `ui`가 있으면 버튼을 우선한다.
- 가능하면 에이전트/후처리에서 목록 요청을 감지해 `reply`를 요약으로 짧게 유지.

### Suggestions for the main list

재사용 우선순위:

1. Dashboard 스펙의 `GET /api/automation_advisor/dashboard/automations` (있으면)
2. 없으면 `GET /api/automation_advisor/suggestions` (또는 chat toolkit과 동일 shape)를 최소 API로 추가
3. 액션: 기존 coordinator / dashboard `action` (`deploy` / `dismiss`) 재사용. 챗 confirm 게이트와 정책이 겹치면 coordinator 서비스를 단일 진입점으로.

리스트 폴링: 뷰 진입 시 1회 fetch, 적용/기각 후 refetch. 실시간 WS는 불필요.

## Error handling

| 상황 | 동작 |
|------|------|
| suggestions API 실패 | 메인에 짧은 오류 문구 + 재시도 |
| 목록 비어 있음 | “추천이 없습니다” 빈 상태 |
| 적용/기각 실패 | 카드 근처 또는 토스트성 메시지, 버튼 재활성화 |
| `ui` 없이 목록만 말로 답함 | 기존 텍스트 버블만 (회귀 아님) |

## Testing (manual)

1. 「추천리스트 보여줘」 → 요약 + 목록 보기만, 긴 표 없음  
2. 목록 보기 → 챗 닫힘, 메인에 그룹된 리스트  
3. 미리보기 적용/기각 → 상태 반영  
4. 배포됨·기각 카드에 적용 버튼 없음  
5. 다른 질문(상태/로그)은 기존처럼 텍스트/`pending`만

## Success criteria

- 목록 요청 시 채팅 토큰·가독성 부담이 표 나열 대비 크게 줄어든다.
- 사용자는 한 번의 클릭으로 Advisor 메인 리스트에 도달한다.
- 미리보기 적용/기각이 메인 리스트에서 가능하다.
