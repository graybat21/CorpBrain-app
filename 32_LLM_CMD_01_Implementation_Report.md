# [보고서] LLM-CMD-01: LLM 엔진 설정(Option A/B) 변경 및 DB 저장 구현 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **작업 브랜치**: `feat/llm-cmd-01-config-db`
- **수명주기 상태**: **Done (Draft PR Created - Closes #27)**

---

## 1. 구현 및 검증 요약

`REQ-FUNC-007` 및 `DEC-10`, `DEC-12`, `DEC-16` 지침을 준수하여 LLM 엔진 선택(Option A/B), 모델 및 타임아웃/단가 설정 관리(`App_Config` 테이블) 및 Windows DPAPI 기반 API Key 암호화/복호화 모듈을 구현하였습니다.

### 🔑 주요 반영 사안
1. **`App_Config` 전역 설정 백엔드 (`ConfigManager`)**:
   - `llm_mode` (Option A / Option B), `llm_cloud_model` (`claude-sonnet-5`), 타임아웃 3종 (`llm_timeout_connect`, `llm_timeout_read`, `llm_timeout_embedding`), 단가 설정 등 관리 (`DEC-10`).
2. **Windows DPAPI 기반 비밀 키 암호화 (`DEC-12`)**:
   - `ctypes` 기반 `CryptProtectData` 호출을 통해 Anthropic API Key를 DPAPI로 암호화 후 Base64로 `App_Config['api_key_encrypted']`에 저장.
   - DB상에 평문 API 키가 존재하지 않음을 검증.
   - 복호화(`CryptUnprotectData`)는 API 호출 직전 메모리상에서만 수행되며 `is_api_key_configured()`를 통해서 존재 유무만 노출.

---

## 2. 검증 결과

- **Pytest 실행 결과**: **4개 테스트 100% 통과** (`tests/test_llm_cmd_01.py`)
  - `test_scenario_1_default_config_initialization`: 기본 설정값 초기화 검증.
  - `test_scenario_2_dpapi_api_key_encryption`: DPAPI 암복호화 동작 검증.
  - `test_scenario_3_plaintext_key_absent_in_db`: DB 내 평문 키 미저장 검증.
  - `test_scenario_4_mode_change_and_price_edit`: 엔진 모드 변경 및 단가 수정 검증.
