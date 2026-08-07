---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-QRY-01: 선택된 엔진(Cloud/Ollama) 연결 상태 확인 (Health Check) 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-QRY-01] LLM 엔진 Health Check
- 목적: 현재 선택된 엔진(Cloud API 또는 Local Ollama)과 정상적으로 통신이 가능한지 핑(Ping)을 날려 상태를 반환한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-011`
- **확정 사항: `DEC-13`** — 데몬 응답과 **모델 보유 여부를 분리 판정**하고, 응답에 `embedding_model_ready` / `generation_model_ready`를 노출
- **확정 사항: `DEC-12`** — Option A 체크는 `api_key_configured` 여부와 어댑터의 `health_check()`로 수행

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **모든 통신은 `NetworkGuard` 경유 (`DEC-15`)**: Option A 체크는 `purpose='llm_cloud'`, Option B 체크는 `purpose='llm_local'`로 호출한다. 이 모듈에서 `httpx`·`requests`를 직접 import하면 CI 린트가 실패한다
- [ ] Option A인 경우: API 키 설정 여부 + Anthropic 어댑터 `health_check()` 호출 (평문 키를 응답·로그에 남기지 않는다 — `DEC-12`)
- [ ] Option B인 경우: 로컬 호스트(`http://127.0.0.1:11434`)의 Ollama 서버 Ping 동작 확인
- [ ] **모델 보유 여부를 별도 판정 (`DEC-13`)**: `GET /api/tags` 결과를 `App_Config['local_embedding_model']` / `local_generation_model`과 비교해 `embedding_model_ready` / `generation_model_ready`를 각각 반환한다. 데몬이 살아 있어도 모델이 없으면 분석은 실패하므로 두 값을 하나로 합치지 않는다
- [ ] 데몬은 응답하지만 필요 모델이 없는 경우 `LLM_PROVISION_REQUIRED`를, 데몬 자체가 무응답이면 `LLM_UNAVAILABLE`을 구분해 매핑한다

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 데몬 미실행 시 체크
- Given: 설정이 Option B(Ollama)로 지정되어 있으나 백그라운드 프로세스가 내려가 있음
- When: Health Check 쿼리를 실행함
- Then: 연결 시간 초과(Timeout) 등을 감지하여 `status: false` 응답을 반환한다.

Scenario 2: 데몬은 정상이나 모델 미보유 (DEC-13)
- Given: Ollama 데몬은 응답하지만 `nomic-embed-text`가 설치되지 않은 환경
- When: Health Check 쿼리를 실행함
- Then: 데몬 상태는 정상으로, `embedding_model_ready: false`로 각각 구분되어 반환되고 UI가 프로비저닝을 안내한다.

Scenario 3: Option A 사용자도 임베딩 모델 필요 (DEC-06 파급)
- Given: Option A(클라우드)로 설정되고 API 키가 유효하나 Ollama가 없는 환경
- When: Health Check 쿼리를 실행함
- Then: `option_a`는 정상이지만 `embedding_model_ready: false`가 반환되어, **심층 분석이 불가함**을 사용자가 사전에 인지할 수 있다.

## :construction: Dependencies & Blockers
- Depends on: API-003
