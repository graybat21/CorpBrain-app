# [보고서] DL-CMD-02 / SCAN-QRY-01 / WS-QRY-01 / DL-QRY-01 / RN-QRY-01 Backend Query & DeepLink Open 구현 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **작업 브랜치**: `feature/backend-queries-and-deeplink-open`
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issues #18, #46, #65, #21, #42 실시간 갱신 완료)

---

## 1. 구현 개요

본 태스크는 SRS `REQ-FUNC-006, 015, 021, 022` 및 `GRILL_LEDGER.md` (DEC-03, DEC-08) 규격에 준수하여, 딥링크 파일 열기 IPC 커맨드, Broken 링크 검증, 스캔 통계, 워크스페이스 목록, Rename Diff 조회 쿼리 서비스 전체를 구현한 건입니다.

### 🔑 주요 핵심 반영 사안

1. **`DL-CMD-02` `os.startfile` IPC 파일 열기 (REQ-FUNC-021 / DEC-08)**:
   - API가 절대 경로를 파라미터로 받지 않고 `file_id`만 수신하여 경로 주입 차단.
   - `File_Meta.current_path` Late Binding 조회 후 `os.startfile()` 호출 (Rename 후에도 최신 경로로 열림).
   - `NOT_FOUND` / `PATH_NOT_ACCESSIBLE` DEC-03 준수 에러 코드 반환.

2. **`DL-QRY-01` 딥링크 Broken 여부 검증 (REQ-FUNC-022)**:
   - `file_id → current_path` 조회 후 `os.path.exists()` 실시간 검사.
   - `is_broken: true/false` + `reason` 필드 포함 DTO 반환.

3. **`SCAN-QRY-01` 스캔 통계 조회 (REQ-FUNC-006)**:
   - 스캔된 파일 수, 총 용량(MB), 예상 분석 소요시간(초) 산출.
   - 예상 소요시간 = `file_count × 100ms` 기준.

4. **`WS-QRY-01` 워크스페이스 목록 및 상세 조회**:
   - `GET /api/v1/workspaces` 전체 목록 반환.
   - `WorkspaceQueryService.get_workspace(id)` 단일 상세 조회 지원.

5. **`RN-QRY-01` Rename Diff 조회**:
   - 가장 최근 `pending` 상태의 `Rename_History` 항목에서 Old/New 파일명 매핑 목록 반환.

---

## 2. 검증 결과

- **Pytest 실행 결과**: **총 68개 전체 자동화 테스트 100% 통과** (실행시간: 9.46초)
  - `test_scenario_1~6`: DL-CMD-02 열기 성공, NOT_FOUND, PATH_NOT_ACCESSIBLE, Broken 링크 상태 조회, 스캔 통계, 워크스페이스 목록 전체 검증.
