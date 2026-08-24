# Automation Advisor

**장비 능력·내 습관에 맞는 Home Assistant 자동화를 추천하고, 승인한 것만 시험 모드로 등록합니다.**

v1은 사용 로그 없이 카탈로그로 바로 추천합니다. v2는 **내 수동 조작만** 로컬 SQLite에 모아 습관 패턴을 만듭니다. YAML은 LLM이 만들지 않습니다.

UX(설치, 스캔, 알림, 센서, `deploy` / `dismiss` / `feedback` / `delete`)는 [HA Rhythm](https://github.com/wizz666/homeassistant-ha-rhythm)과 비슷합니다. 추천 방식은 다릅니다.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

---

## Rhythm · Suggester와 다른 점

| | Automation Advisor (이 프로젝트) | HA Rhythm | AI Automation Suggester |
|---|---|---|---|
| v1 근거 | 지금 있는 장비 + 내장 카탈로그 | Recorder 7일+ 습관 | 현재 엔티티 스냅샷을 LLM에 전달 |
| YAML 작성 | **Deterministic compiler** | LLM이 자동화 JSON/YAML 생성 | LLM이 YAML 창작 |
| 설치 직후 | **바로 스캔 가능** | 이력 필요 | 바로 가능 (환각 가능) |
| 안전 | lock / climate / 전열 등 **액션 차단** | 제한 약함 | 모델 판단 |
| 등록 | `initial_state: false` **시험 모드** | 파일에 바로 넣고 reload | 사용자가 YAML 붙여넣기 |
| 승인 | apply / dismiss / kill switch | deploy / dismiss | 복사 |
| 습관 학습 | v2 로컬 Observe + Pattern (행위자 판별) | v1부터 Recorder | 없음 |
| 커뮤니티 비율 | 로컬 스텁 JSON (실서버 집계 없음) | — | — |

이 시스템은 Matter를 직접 다루지 않습니다. 기기 상태·실행은 Home Assistant의 일입니다.

---

## 문서

- 한 장 구성(기능·모듈): [`docs/briefing/system-overview.md`](docs/briefing/system-overview.md) · PDF [`docs/briefing/system-overview.pdf`](docs/briefing/system-overview.pdf) · 슬라이드 [`docs/briefing/system-overview.pptx`](docs/briefing/system-overview.pptx)
- PRD: [`docs/prd/automation-advisor-prd.md`](docs/prd/automation-advisor-prd.md) · PDF [`docs/prd/automation-advisor-prd.pdf`](docs/prd/automation-advisor-prd.pdf)
- 플로우차트 PDF: [`docs/flowcharts.pdf`](docs/flowcharts.pdf)
- 시퀀스 PDF: [`docs/system-architecture-sequence.pdf`](docs/system-architecture-sequence.pdf)
- PlantUML 원문: `docs/diagrams/*.puml`

---

## 설치 (HACS 커스텀 저장소)

이 코드는 **GitHub 플러그인 스토어에 올라간 상태가 아닙니다.** 실제 기기 테스트는 **본인 Home Assistant `/config`에 폴더를 넣는 방식**입니다.

예: 이 프로젝트에서 쓰던 HA는 `https://ha.chanuk.theworkpc.com/` (HA OS, LAN `172.30.1.99`) 입니다. **그 서버의** `/config/custom_components/automation_advisor/` 에 이 레포 폴더를 복사해야 동작합니다. Mac에만 코드가 있으면 HA에서는 안 보입니다.

1. `custom_components/automation_advisor/` → HA `/config/custom_components/automation_advisor/` 복사 (Samba / File editor / SSH).
2. Home Assistant 재시작.
3. 설정 → 기기 및 서비스 → 통합 추가 → **Automation Advisor**.
4. 옵션: 시험 모드, 습관 학습, 최소 관찰 일수(기본 7), 커뮤니티 스텁, (선택) LLM API 키.

HACS를 쓰려면 Custom repositories에 이 저장소를 Integration으로 추가한 뒤 설치·재시작하면 됩니다.

---

## 한 번만 할 설정

배포한 자동화가 적용되려면 `configuration.yaml`에 다음을 넣고 **한 번** 재시작합니다.

```yaml
automation advisor: !include automation_advisor.yaml
```

통합이 처음 로드될 때 빈 `automation_advisor.yaml`을 만들어 두므로 include가 깨지지 않습니다. 그다음부터는 deploy 시 자동화 reload만 하면 됩니다.

---

## 사용 흐름

설치 후 환영 알림이 뜹니다. Companion 앱이 있으면 알림 버튼으로 승인합니다. 디스코드는 필요 없습니다.

### 1. 스캔

개발자 도구 → 동작 → `automation_advisor.scan` → 실행.

v1 카탈로그는 Recorder를 읽지 않습니다. v2 습관 학습은 **스캔할 때마다** Home Assistant Recorder에서 learnable 수동 조작 이력을 SQLite로 백필한 뒤(중복 제외), 실시간 Observer와 합쳐 패턴을 찾습니다.

### 2. 지금 한 번 실행

Companion 앱에 **실행하시겠습니까?** 가 뜹니다. [실행]을 누르면 컴파일된 액션만 **즉시 한 번** 호출합니다. 자동화는 아직 안 넣습니다.

앱이 없으면 `automation_advisor.run_once`에 suggestion ID를 넣습니다.

### 3. 그다음 자동화

실행이 끝난 뒤에 **자동화하시겠습니까?** 를 다시 묻습니다. [자동화]면 시험 모드(`initial_state: false`)로 등록합니다. [아니요]면 기각합니다.

---

## 대시보드 카드 (복붙)

Lovelace 대시보드 원시 YAML에 넣습니다.

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >
      ## Automation Advisor
      내 장비 × 카탈로그. YAML은 컴파일러가 작성합니다.
      승인 전에는 Home Assistant에 넣지 않습니다.
  - type: entities
    entities:
      - entity: sensor.automation_advisor_status
        name: Status
      - entity: sensor.automation_advisor_catalog_matches
        name: Catalog matches
      - entity: sensor.automation_advisor_pending_suggestions
        name: Pending suggestions
      - entity: sensor.automation_advisor_deployed_automations
        name: Deployed automations
  - type: button
    name: Run scan
    icon: mdi:magnify-scan
    tap_action:
      action: perform-action
      perform_action: automation_advisor.scan
      data: {}
  - type: button
    name: Kill switch
    icon: mdi:power
    tap_action:
      action: perform-action
      perform_action: automation_advisor.kill_switch
      data: {}
```

스캔 알림의 suggestion ID로 `automation_advisor.deploy` / `dismiss`를 호출합니다.

---

## 동작

| 동작 | 설명 |
|---|---|
| `automation_advisor.scan` | 장비 스냅샷 × 카탈로그. 이력 없음 |
| `automation_advisor.run_once` | 지금 한 번만 실행. 자동화는 등록하지 않음 |
| `automation_advisor.deploy` | `suggestion_id`를 `automation_advisor.yaml`에 시험 등록 |
| `automation_advisor.dismiss` | 같은 레시피·장비 조합을 **3일** 동안 다시 추천하지 않음 (이후 스캔에서 다시 가능) |
| `automation_advisor.feedback` | `good` / `bad` |
| `automation_advisor.delete` | 추천·배포된 YAML 항목 삭제 |
| `automation_advisor.kill_switch` | 이 시스템이 등록한 자동화를 모두 제거 |
| `automation_advisor.habit_status` | 로컬 습관 이벤트 수·관찰 일수 |
| `automation_advisor.clear_habit_data` | 로컬 습관 SQLite 삭제 |

---

## 센서

| 엔티티 | 설명 |
|---|---|
| `sensor.automation_advisor_status` | `idle` / `scanning` |
| `sensor.automation_advisor_catalog_matches` | 이번 스캔의 카탈로그 매칭 수 |
| `sensor.automation_advisor_pending_suggestions` | 검토 대기 |
| `sensor.automation_advisor_deployed_automations` | 등록된 (시험) 자동화 |

---

## v1이 추천하는 것

내장 `recipes.json` 예시:

- 같은 방 움직임/재실 → 조명 켜기 / 10분 없으면 끄기
- 습도 + 팬 → 환기
- 누수 센서 → 알림 (잠금장치는 건드리지 않음)
- 문/창이 오래 열림 → 알림
- 일몰 → 조명 켜기

액션으로 막히는 도메인: `lock`, `alarm_control_panel`, `camera`, `climate`, `water_heater`, `vacuum`.

이미 같은 엔티티 집합을 쓰는 자동화가 있으면 그 레시피는 건너뜁니다.

---

## 파일

- 추천 저장: `/config/.automation_advisor_suggestions.json`
- 배포 YAML: `/config/automation_advisor.yaml` — 컴파일러 출력. 직접 고치지 마세요.

LLM은 YAML을 쓰지 않습니다. 설명만 선택적으로 붙일 수 있고, v1 카탈로그는 문구·스텁 비율을 씁니다.

### 로컬 LLM (Spark vLLM)

통합 옵션에 다음을 넣으면 습관 추천 설명이 Spark vLLM을 씁니다.

| 옵션 | 예 |
|---|---|
| LLM Base URL | `http://<spark-lan-or-tailscale>:8000/v1` |
| LLM 모델 | `/v1/models`에 나오는 id |
| API 키 | vLLM은 보통 비움 |

HA가 Spark `:8000`에 HTTP로 닿아야 합니다. 같은 LAN이면 LAN IP, Tailscale만 되면 Tailscale IP. 실패 시 카탈로그/패턴 문구로 fallback합니다.

### v2 습관 학습

- 수동 UI(`user_id`)·허용 물리 스위치만 학습. 자동화/Advisor 실행은 제외.
- 저장: `/config/.automation_advisor_events.db` (기본 30일 보관).
- 기본 **7일** 관찰 후 A→B 패턴(support/confidence/lift)이 스캔에 붙습니다.
- 데모 때 빨리 보려면 옵션에서 `min_observe_days`를 1로 낮추면 됩니다.
- 커뮤니티 “68%”는 **로컬 스텁**입니다. 다른 집 실서버 집계는 없습니다.

습관 학습과 카탈로그 스캔은 같은 승인 게이트(실행할까요 → 자동화할까요)를 씁니다.
