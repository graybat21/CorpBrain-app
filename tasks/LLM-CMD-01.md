---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-CMD-01: LLM 엔진 설정(Option A/B) 변경 및 DB 저장"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-CMD-01] 하이브리드 LLM 설정 관리 (Command)
- 목적: 사용자가 클라우드 API(Option A)와 로컬 프라이빗(Option B - Ollama) 중 선호하는 엔진을 선택하면 이 설정을 데이터베이스에 저장한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `REQ-FUNC-007`
- DTO 명세: `API-003`
- **확정 사항: `DEC-10`** — 전역 설정 테이블은 `App_Config` 단일안
- **확정 사항: `DEC-12`** — Option A는 Anthropic `claude-sonnet-5` 단일, API 키는 Windows DPAPI 암호화
- **확정 사항: `DEC-16`** — 단가는 마이그레이션 시드값 + 기준일 병기 + 사용자 편집 가능(자동 갱신 없음), 타임아웃도 `App_Config` 키

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option A/B Enum 정의 및 **`App_Config`** 테이블에 업데이트하는 로직 구현 (`key='llm_mode'`). `Settings_Meta`라는 테이블은 존재하지 않는다 — 전역 설정 테이블명은 `App_Config` 단일안이다 (`DEC-10`)
- [ ] Option B(Ollama) 선택 시 내부적으로 로컬 데몬 구동 여부 플래그를 활성화하도록 연계
- [ ] **API 키 저장은 Windows DPAPI로 암호화 (`DEC-12`)**: `ctypes`로 `CryptProtectData` 호출 → blob을 base64 인코딩 → `App_Config['api_key_encrypted']`. **신규 라이브러리를 추가하지 않는다**
- [ ] 복호화(`CryptUnprotectData`)는 **API 호출 직전 메모리에서만** 수행하고 즉시 폐기한다. 평문 키를 인스턴스 변수·로그·에러 응답에 남기지 않는다
- [ ] 복호화 실패(다른 사용자 계정·다른 PC로 DB 이전) 시 **키 재입력 유도** 상태로 전이한다. 조용히 무시하거나 빈 키로 API를 호출하지 않는다
- [ ] `App_Config`에 `llm_cloud_model`(기본 `claude-sonnet-5`)·`cloud_price_input_per_mtok`·`cloud_price_output_per_mtok` 키를 초기화한다 (`DEC-12` — 모델명·단가 하드코딩 금지)
- [ ] **단가 시드값과 기준일 (`DEC-16`)**: 단가 초기값은 **마이그레이션(`migrations/vNNN_*.sql`) 시드**로 주입하고 `cloud_price_updated_at`(ISO-8601 UTC)에 기준일을 함께 저장한다. 설정 화면에서 사용자가 단가를 직접 편집할 수 있게 하며, 편집 시 `cloud_price_updated_at`을 갱신한다. **가격표를 네트워크로 조회하지 않는다** (`DEC-15`의 네 번째 목적지가 된다)
- [ ] **타임아웃 키 초기화 (`DEC-16`)**: `llm_timeout_connect`(10), `llm_timeout_read`(120), `llm_timeout_embedding`(30) — 단위는 초. 저사양 PC의 로컬 추론 지연을 사용자가 조정할 수 있어야 하므로 코드에 하드코딩하지 않는다
- [ ] `App_Config`에 `local_embedding_model`(기본 `nomic-embed-text`)·`local_generation_model`(기본 `qwen2.5:7b-instruct`) 키를 초기화한다 (`DEC-13` — 모델명 하드코딩 금지)
- [ ] **Option A를 선택해도 임베딩용 Ollama는 필요하다**(`DEC-06`·`DEC-13`). 설정 화면 문구에서 "Option A = Ollama 불필요"로 오인되지 않도록 임베딩 모델 요구사항을 별도로 안내한다

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 정상적인 엔진 변경 요청
- Given: 현재 Option A 상태인 시스템
- When: 사용자가 Option B로 설정을 변경하는 요청을 보냄
- Then: DB에 설정이 'Option B'로 반영되고 성공 응답(200 OK)이 반환된다.

## :test_tube: Acceptance Criteria (추가)
Scenario 2: API 키 평문 미저장 검증 (DEC-12)
- Given: 사용자가 설정 화면에서 API 키를 입력함
- When: `corpbrain_meta.db`를 바이너리로 열어 검색함
- Then: 입력한 키 문자열이 **DB 어디에도 평문으로 존재하지 않으며**, `api_key_encrypted`에는 DPAPI blob의 base64만 저장되어 있다.

Scenario 3: 다른 계정 복호화 실패 처리 (DEC-12)
- Given: 다른 Windows 사용자 계정에서 생성된 `api_key_encrypted` 값이 주어짐
- When: 복호화를 시도함
- Then: `CryptUnprotectData` 실패를 감지해 **키 재입력 유도 상태**로 전이하고, 빈 키로 API를 호출하지 않는다.

## :gear: Technical & Non-Functional Constraints
- 무결성: Enum에 존재하지 않는 엔진 값이 들어올 경우 예외 처리 필수
- **비밀 취급 (`DEC-12`)**: API 키는 응답 DTO에 절대 포함하지 않는다. 설정 조회 응답은 `api_key_configured: true/false` 같은 **존재 여부만** 노출한다 (마스킹된 일부 문자도 반환하지 않는다)

## :checkered_flag: Definition of Done (DoD)
- [ ] 단위 테스트 작성 및 통과
- [ ] Swagger 스펙상 유효한 값만 전송되도록 Validation 적용

## :construction: Dependencies & Blockers
- Depends on: DB-001, API-003
- Blocks: LLM-CMD-02, LLM-CMD-03
