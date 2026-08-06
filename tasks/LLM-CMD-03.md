---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-CMD-03: Ollama 프로비저닝 (assisted 무인 설치 / detect_only 폐쇄망 탐지)"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-CMD-03] Ollama 프로비저닝
- 목적: **정상 상태(steady state)의 완전 오프라인 동작**을 위해 준비 단계에서 Ollama 데몬과 필요 모델을 확보한다. 네트워크 가용 시 백그라운드 무인 설치·Pull(`assisted`)을 수행하고, **폐쇄망에서는 사전 프로비저닝된 환경을 탐지만 한다(`detect_only`)**.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-010`, `REQ-FUNC-011`, `REQ-NF-005`
- **확정 사항: `DEC-13`** — 모델 2종 역할 분리(임베딩 `nomic-embed-text` / 생성 `qwen2.5:7b-instruct`) + 프로비저닝 2모드
- **확정 사항: `DEC-04`** — 202 + `task_id` 즉시 반환, 1초 폴링
- **확정 사항: `DEC-15`** — 인스톨러·모델 다운로드는 `NetworkGuard`의 `purpose='provisioning'`으로만 나간다. 이 모듈에서 HTTP 라이브러리를 직접 import하면 CI 린트가 실패한다

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 현재 OS(Windows) 타겟 환경에 맞는 Ollama 설치 여부 확인 (PATH 조회 + 레지스트리 검색)
- [ ] **프로비저닝 모드 자동 판정 (`DEC-13`)**: 인스톨러 URL 도달성 사전 확인(`NetworkGuard.is_reachable(purpose='provisioning', ...)` — HEAD, 5초 타임아웃) → 도달 가능하면 `assisted`, 불가하면 `detect_only`. 판정 결과를 `Async_Task.result_json.provision_mode`에 기록
- [ ] `assisted` 모드: Installer 다운로드(`NetworkGuard.stream(purpose='provisioning', ...)`) 및 무인(Silent) 실행 스크립트 트리거 로직 구현. 화이트리스트 외 호스트로 리다이렉트되면 `EgressBlockedError`로 차단되므로 이를 `LLM_PROVISION_REQUIRED`로 매핑한다 (`DEC-15`)
- [ ] **`detect_only` 모드: 설치·다운로드를 일절 시도하지 않는다.** 데몬·모델 탐지만 수행하고, 미준비 시 `error_code='LLM_PROVISION_REQUIRED'`로 즉시 실패 종료하며 필요 모델 목록과 오프라인 설치 절차를 안내한다 (**재시도 루프 금지**)
- [ ] **필요 모델 판정 (`DEC-13`)**: `GET /api/tags`로 보유 모델을 조회한다. `purpose='embedding'`이면 `App_Config['local_embedding_model']`(기본 `nomic-embed-text`)만, `purpose='generation'`이면 추가로 `App_Config['local_generation_model']`(기본 `qwen2.5:7b-instruct`)까지 검사한다. **모델명을 코드에 하드코딩하지 않는다**
- [ ] `assisted` 모드에서 누락 모델에 대해 `ollama pull <model>` Subprocess 실행 및 표준 출력(stdout) 파싱
- [ ] 진행 상황을 **`Async_Task` 테이블에 `task_type='llm_onboard'`로 영속화**하고 `GET /api/v1/analyze/{task_id}/progress` 폴링으로 노출 (`DEC-04`). **WebSocket·SSE를 도입하지 않는다.**
- [ ] 진행률 문구에서 임베딩 모델(~274MB)과 생성 모델(~4.7GB)을 **구분해 표시**한다 (두 모델을 하나의 덩어리로 합산 표시 금지 — `DEC-06` 파급)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 네트워크 가용 환경에서 자동 설치 트리거 (assisted)
- Given: Ollama가 설치되지 않았고 인스톨러 URL에 도달 가능한 Windows 환경
- When: `POST /api/v1/llm/onboard { purpose: 'generation' }`을 호출함
- Then: **202 Accepted + `task_id`가 즉시 반환**되고 `provision_mode='assisted'`로 기록되며, 설치·Pull이 백그라운드에서 실행되어 진행 상태가 progress 폴링으로 지속 갱신된다.

Scenario 2: 폐쇄망 — 사전 프로비저닝 환경 탐지 (detect_only, DEC-13)
- Given: 인터넷이 차단되어 있으나 관리자가 Ollama와 `nomic-embed-text`를 사전 설치한 PC
- When: `POST /api/v1/llm/onboard { purpose: 'embedding' }`을 호출함
- Then: `provision_mode='detect_only'`로 판정되고, **인스톨러 다운로드를 시도하지 않고** `GET /api/tags` 탐지만으로 작업이 `status='completed'`가 된다.

Scenario 3: 폐쇄망 — 모델 미준비 시 즉시 실패 (DEC-13)
- Given: 인터넷이 차단되어 있고 필요 모델이 없는 PC
- When: 온보딩 작업이 실행됨
- Then: **재시도·무한 대기 없이** `Async_Task.status='failed'` + `error_code='LLM_PROVISION_REQUIRED'`로 종료되고 필요 모델 목록이 사용자에게 노출된다. **Option A로 자동 폴백하지 않는다.**

## :gear: Technical & Non-Functional Constraints
- **REQ-NF-005 경계 (`DEC-13`)**: 준비 단계의 인스톨러·모델 바이너리 다운로드는 허용되지만, **분석 대상 문서의 내용·경로를 어떤 형태로도 함께 전송하지 않는다**(User-Agent·쿼리 파라미터 포함). 프로비저닝 완료 후 정상 상태에서 `127.0.0.1` 외 목적지 통신은 0건이어야 한다 (TC-SEC-002)
- 모델 가중치를 exe에 번들하거나 자체 포맷으로 재배포하지 않는다 (CON-02). 오프라인 경로는 문서화된 `%USERPROFILE%\.ollama\models` 복사 절차다
- Subprocess 실행 시 콘솔 창을 노출하지 않는다 (`CREATE_NO_WINDOW`). 실패는 `subprocess.CalledProcessError`를 구체적으로 포착해 로깅하며 bare `except:`를 쓰지 않는다

## :construction: Dependencies & Blockers
- Depends on: API-003
- Blocks: LLM-FE-02
