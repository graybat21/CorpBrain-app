---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-FE-02: Ollama 설치 프로그레스 및 Health Check 상태 아이콘"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-FE-02] LLM 온보딩 및 상태 UI
- 목적: Option B(Ollama) 선택 시 백그라운드 설치 진행률과 LLM 엔진 Health Check 상태를 사용자에게 시각적으로 제공한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.2 → **REQ-FUNC-010, 011** (Local LLM Provisioning, Health Check)
- API 명세: API-003
- **확정 사항: `DEC-13`** — 모델 2종 역할 분리 표시 + 프로비저닝 2모드(`assisted` / `detect_only`)
- **확정 사항: `DEC-04`** — `POST /api/v1/llm/onboard`는 `202` + `task_id`만 반환하므로 진행률은 **1초 폴링**으로 얻는다

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option B 선택 시 Ollama 미설치 감지 후 인라인 프로그레스 바(0~100%) 컴포넌트 렌더링
- [ ] **진행률은 `POST /api/v1/llm/onboard` 응답이 아니라 `GET /api/v1/analyze/{task_id}/progress` 1초 폴링에서 읽는다** (`DEC-04`). POST 응답에서 `status`/`progress_pct`를 기대하지 않는다
- [ ] **모델 2종을 구분해 표시 (`DEC-13`)**: "임베딩 모델(약 274MB — 모든 사용자 필수)"과 "생성 모델(약 4.7GB — Option B 전용)"을 별도 항목으로 렌더링한다. 두 다운로드를 하나의 합산 프로그레스로 묶지 않는다 (4.7GB 진행률에 274MB가 섞여 사용자가 남은 시간을 오판한다)
- [ ] **Option A 사용자에게도 임베딩 모델 준비 상태를 노출 (`DEC-06` 파급)**: `embedding_model_ready: false`면 심층 분석 버튼을 비활성화하고 이유를 표시한다
- [ ] **`detect_only` 모드 분기 UI (`DEC-13`)**: `provision_mode='detect_only'`이면 프로그레스 바 대신 **"폐쇄망 감지 — 수동 프로비저닝 필요"** 안내와 필요 모델 목록(`nomic-embed-text`, `qwen2.5:7b-instruct`)·오프라인 설치 절차를 표시한다. **이 모드에서는 "설치 재시도" 버튼을 제공하지 않는다** (인터넷이 없는 환경에서 눌러도 실패만 반복된다)
- [ ] 5초 주기 Health Check 폴링으로 ✅/❌ 상태 아이콘 토글
- [ ] `assisted` 모드의 설치 실패 시에만 재시도 버튼 및 에러 메시지 표시

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 설치 프로그레스 표시
- Given: Option B 선택 상태이며 Ollama 미설치, 네트워크 도달 가능(`assisted`)
- When: 분석을 시도함
- Then: 인라인 프로그레스 바(0~100%)가 표시되고 터미널이 노출되지 않는다.

Scenario 2: Health Check 상태 아이콘
- Given: Option B이며 Ollama 데몬이 정상 구동 중
- When: 5초 주기 Health Check 폴링이 실행됨
- Then: 설정 패널에 ✅ 상태 아이콘이 표시된다.

Scenario 3: 폐쇄망 안내 분기 (DEC-13)
- Given: `provision_mode='detect_only'`이고 필요 모델이 없어 작업이 `LLM_PROVISION_REQUIRED`로 실패함
- When: 온보딩 화면을 확인함
- Then: 프로그레스 바 대신 수동 프로비저닝 안내와 필요 모델 목록이 표시되고, **설치 재시도 버튼은 노출되지 않는다.**

Scenario 4: 모델 2종 구분 표시 (DEC-13)
- Given: 임베딩·생성 모델이 모두 미설치인 `assisted` 환경
- When: 온보딩 진행 중 화면을 확인함
- Then: 임베딩 모델과 생성 모델의 진행률이 **각각 별도 항목**으로 표시되며, 하나의 합산 퍼센트로 표시되지 않는다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-010 — 백그라운드 설치, 진행률 실시간 갱신 (폴링 기반, WebSocket·SSE 금지 — `DEC-04`)
- 가용성: REQ-NF-010 — LLM 미연결 시에도 설정 UI 정상 동작
- 보안 문구: 프로비저닝이 인터넷을 사용한다는 사실을 숨기지 않고 명시한다. 단, **문서 내용은 전송되지 않음**을 함께 안내한다 (`DEC-13` / REQ-NF-005)

## :checkered_flag: Definition of Done (DoD)
- [ ] `assisted` 설치 실패 시 ❌ 아이콘 및 재시도 버튼 제공 (`detect_only`에서는 미제공)
- [ ] LLM-CMD-03 Progress API 연동 완료 (1초 폴링)

## :construction: Dependencies & Blockers
- Depends on: API-003, LLM-CMD-01, LLM-CMD-03
- Blocks: None
