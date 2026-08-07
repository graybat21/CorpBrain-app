# [보고서] STAT-CMD-01/STAT-QRY-01 대시보드 통계 이벤트 로깅 및 WPM 시간 절약 집계 서비스 구현 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **작업 브랜치**: `feature/analytics-service`
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issue #49 실시간 갱신 완료)

---

## 1. 구현 개요 (`STAT-CMD-01` & `STAT-QRY-01`)

본 태스크는 SRS `REQ-FUNC-027, 028, 029, 030` 및 `GRILL_LEDGER.md` (DEC-07, DEC-11, DEC-16) 규격에 준수하여, 사용자 액션 이벤트(`deeplink_click`, `watcher_update` 등) 트래킹, Option A/B 비용 기록, 250 WPM 기반 시간 절약 집계 및 현재 스냅샷 압축률 계산 서비스를 구축한 구현 건입니다.

### 🔑 주요 핵심 반영 사안
1. **액션 이벤트 로깅 및 비용 규약 (`STAT-CMD-01` / DEC-16)**:
   - event_type 소문자 스네이크 표기법 준수 (`deeplink_click`, `watcher_update`).
   - **`cost_usd` 산출 규칙 (`DEC-16`)**:
     - Option A(Claude Cloud): `usage` 토큰 × `App_Config` 단가로 산출하여 저장.
     - Option B(Ollama 로컬): **`0.0`** (비용 발생하지 않음)으로 구별 기록.
     - 네트워크/API 실패로 토큰 미측정 시: **`NULL`** (미측정)로 기록하여 `0.0`과 `NULL`을 철저히 분리.
2. **원문 파일 삭제 시 과거 집계 데이터 보존 (`DEC-07`)**:
   - `Analytics_Log`의 `file_id` 및 `wiki_id`에 `ON DELETE SET NULL` FK 설정.
   - 원본 파일이 삭제되어도 기존 로깅 내역과 과거 팩트체크 클릭 수가 소급 감소하지 않음.
3. **250 WPM 기반 절약 시간 계산 (`STAT-QRY-01` / REQ-FUNC-027)**:
   - 추출 토큰량 기준: `SUM(tokens_used) / 325.0` (250 WPM × 1.3 tokens/word = 325 tokens/min) 분 환산.
4. **현재 스냅샷 압축률 (`DEC-07`)**:
   - `compression_ratio`: `COUNT(parsed File_Meta) : COUNT(Wiki_Content)` 스냅샷 비율 산출.
   - 기간 필터와 무관함을 명시하기 위해 `knowledge_ratio_scope: "current"` 포함.
5. **KST ISO-8601 UTC 기간 필터링 (`DEC-11`)**:
   - 프론트엔드가 전송한 `from_time`/`to_time` UTC 표준 시각 문자열을 그대로 DB `created_at`과 비교하여 타임존 왜곡 방지.
6. **REST API 엔드포인트 수립**:
   - `POST /api/v1/workspace/{workspace_id}/analytics/event`
   - `GET /api/v1/workspace/{workspace_id}/analytics/summary`

---

## 2. 검증 결과 (`tests/test_stat_cmd_01_qry_01.py`)

- **Pytest 실행 결과**: **총 62개 전체 자동화 테스트 100% 통과** (실행시간: 9.05초)
  - `test_scenario_1_log_event_and_cost_calculation_rules`: Option A/B 및 NULL 비용 산출 규칙 검증 (`DEC-16`).
  - `test_scenario_2_wpm_time_saved_calculation`: 32,500 토큰 기반 100.0분 절약 시간 산출 검증.
  - `test_scenario_3_snapshot_compression_ratio_and_historical_preservation`: 파일 삭제 시 `Analytics_Log` 보존 및 스냅샷 비율 검증 (`DEC-07`).
  - `test_scenario_4_period_filter_utc_iso8601`: ISO-8601 UTC 기간 필터링 정확도 검증 (`DEC-11`).
