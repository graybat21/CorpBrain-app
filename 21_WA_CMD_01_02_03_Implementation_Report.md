# [보고서] WA-CMD-01/02/03 Watcher 모드 관리, watchdog 이벤트 감지 및 증분 재분석 파이프라인 구현 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **작업 브랜치**: `feature/watcher-service`
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issues #53, #54, #55 실시간 갱신 완료)

---

## 1. 구현 개요 (`WA-CMD-01`, `WA-CMD-02`, `WA-CMD-03`)

본 태스크는 SRS `REQ-FUNC-023, 024, 025, 026` 및 `GRILL_LEDGER.md` (DEC-08, DEC-09) 규격에 준수하여, 물리 디렉토리 감시 데몬(`watchdog`), 모드 설정(Manual/Realtime/Idle/Off 4종), 디바운싱 필터링, 파일 이동 시 `file_id` 보존 및 증분 재분석 파이프라인을 완료한 구현 건입니다.

### 🔑 주요 핵심 반영 사안
1. **Watcher 동작 모드 및 영속성 (`WA-CMD-01` / REQ-FUNC-023)**:
   - `Manual`, `Realtime`, `Idle`, `Off` 4개 동작 모드 제공.
   - `Watcher_Config` SQLite 테이블 백엔드 저장 및 앱 재시작 시 영속성 보장.
2. **`watchdog` 이벤트 디바운싱 및 mtime 대조 (`WA-CMD-02` / REQ-FUNC-024, 026)**:
   - 500ms~1000ms 디바운싱 기반 중복 이벤트 억제.
   - OS `mtime`과 DB `last_modified` 대조로 단순 속성변경(Attribute touch) 필터링.
3. **이동 이벤트(`FileMovedEvent`) 시 `file_id` 보존 (`DEC-08`)**:
   - 파일 이동 시 **신규 `file_id`로 재등록하지 않고 기존 `File_Meta.current_path` 및 `file_name`만 UPDATE**.
   - 위키 딥링크 앵커 `[[file_id:name]]` 및 통계 데이터의 파괴 방지.
4. **증분 재분석 및 큐 처리 파이프라인 (`WA-CMD-03` / REQ-FUNC-025 / DEC-09)**:
   - 수정된 파일 큐(`queue.Queue`) 적재 후 `process_next_queued_item()` 처리.
   - `VectorDBManager.delete_file(file_id)` ➔ `upsert` 순서 고정 (`DEC-09`).
5. **REST API 엔드포인트 수립**:
   - `GET /api/v1/workspace/{workspace_id}/watcher/config`
   - `POST /api/v1/workspace/{workspace_id}/watcher/config`
   - `GET /api/v1/workspace/{workspace_id}/watcher/status` (`WA-QRY-01`)

---

## 2. 검증 결과 (`tests/test_wa_cmd_01_02_03.py`)

- **Pytest 실행 결과**: **총 58개 전체 자동화 테스트 100% 통과** (실행시간: 9.02초)
  - `test_scenario_1_watcher_mode_config_persistence`: 4종 모드 변경 및 SQLite 영속화 검증.
  - `test_scenario_2_watchdog_event_handler_debounce_and_mtime_touch_filtering`: 단순 touch 필터링 및 수정 파일 큐 적재 검증.
  - `test_scenario_3_file_moved_event_preserves_file_id`: 이동 이벤트 발생 시 기존 `file_id` 보존 및 경로 UPDATE 검증 (`DEC-08`).
  - `test_scenario_4_incremental_reanalysis_queue_processing`: 큐 적재 파일 증분 재분석 및 SQLite `parse_status='parsed'` 검증 (`DEC-09`).
