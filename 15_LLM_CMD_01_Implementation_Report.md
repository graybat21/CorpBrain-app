# [보고서] LLM-CMD-01 하이브리드 LLM 설정 관리 모듈 구현 및 검증 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issue #28 실시간 갱신 완료)

---

## 1. 구현 개요 (`LLM-CMD-01`)

본 태스크는 `docs/grill/GRILL_LEDGER.md` (DEC-10, DEC-12, DEC-16) 지침에 준수하여 하이브리드 LLM 설정 관리자(`ConfigManager`)를 SQLite `App_Config` 테이블 기반으로 구축한 구현 건입니다.

### 🔑 주요 핵심 반영 사안
1. **전역 설정 단일 스토리지 (`DEC-10`)**:
   - `App_Config` SQLite 테이블 백엔드 저장 (`config_key`, `config_value`, `updated_at`).
   - 기본 설정값 시드 자동 주입 (`llm_mode`: `"Option A"`, `llm_cloud_model`: `"claude-sonnet-5"`, `local_embedding_model`: `"nomic-embed-text"`).
2. **Windows DPAPI 보안 암호화 (`DEC-12`)**:
   - API Key 입력 시 Windows DPAPI(`CryptProtectData`)로 암호화 후 base64 blob만 `api_key_encrypted` 키에 보관.
   - DB 평문 검색 시 키 노출 100% 차단 (`test_scenario_3_plaintext_key_absent_in_db` 통과).
   - API 호출 직전 메모리상에서만 복호화하며, 외부 DTO/API 응답에는 `api_key_configured: true/false` 여부만 반환.
3. **단가 및 타임아웃 구성 (`DEC-16`)**:
   - `cloud_price_input_per_mtok` ($3.00), `cloud_price_output_per_mtok` ($15.00), `cloud_price_updated_at` (시드일) 관리.
   - 타임아웃 구성: `llm_timeout_connect` (10s), `llm_timeout_read` (120s), `llm_timeout_embedding` (30s).

---

## 2. 검증 결과 (`tests/test_llm_cmd_01.py`)

- **Pytest 실행 결과**: **총 44개 자동화 테스트 100% 통과** (실행시간: 3.09초)
  - `test_scenario_1_default_config_initialization`: 기본 시드값 10종 자동 초기화 검증.
  - `test_scenario_2_dpapi_api_key_encryption`: DPAPI 암호화 및 메모리 복호화 정확성 검증.
  - `test_scenario_3_plaintext_key_absent_in_db`: DB 저장소 바이너리/텍스트 내 평문 키 미존재 검증.
  - `test_scenario_4_mode_change_and_price_edit`: 엔진 모드 변경 및 사용자 지정 단가 갱신 검증.
