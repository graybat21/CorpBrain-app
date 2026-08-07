# [보고서] LLM-CMD-03 LLM 재시도 및 파일 격리 회복성 서비스 구현 및 검증 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issue #30 실시간 갱신 완료)

---

## 1. 구현 개요 (`LLM-CMD-03`)

본 태스크는 `docs/grill/GRILL_LEDGER.md` (DEC-16) 지침에 준수하여 LLM/임베딩 호출 실패 시 시스템 안정성을 보장하는 `LLMResilienceService` 모듈을 구축한 구현 건입니다.

### 🔑 주요 핵심 반영 사안
1. **지수 백오프 기반 재시도 엔진 (`DEC-16`)**:
   - 일시적 네트워크/LLM 타임아웃 발생 시 최대 3회까지 지수 백오프(Exponential Backoff: 1s, 2s, 4s...)로 재시도.
2. **단일 파일 실패 격리 (`HTTP 207 Multi-Status` 개념, `DEC-16`)**:
   - 특정 1개 파일이 손상되었거나 지속 실패하더라도 전체 분석 작업을 중단시키지 않음.
   - 실패한 파일의 `file_id`와 `error_code`만 `failed_files[]` 배열에 누적하고 **다음 파일로 계속 진행**.
3. **연속 실패 상한 서킷 브레이커 (`DEC-16`)**:
   - Ollama 로컬 데몬 다운 등으로 인해 연속 10개 파일이 모두 실패할 경우, 남은 파일 수천 개를 계속 재시도하여 리소스를 낭비하지 않고 `LLM_UNAVAILABLE` 예외를 즉시 발생시키며 작업을 안전 종료.

---

## 2. 검증 결과 (`tests/test_llm_cmd_03.py`)

- **Pytest 실행 결과**: **총 47개 자동화 테스트 100% 통과** (실행시간: 3.66초)
  - `test_scenario_1_transient_error_retry_and_recovery`: 일시 오류 2회 발생 후 3회차 성공 검증.
  - `test_scenario_2_single_file_isolation_in_batch`: 10개 중 1개 파일 실패 시 9개 정상 완료 및 `multi_status` 반환 검증.
  - `test_scenario_3_consecutive_failures_circuit_breaker`: 10건 연속 실패 시 서킷 브레이커 작동 및 `LLM_UNAVAILABLE` 예외 발생 검증.
