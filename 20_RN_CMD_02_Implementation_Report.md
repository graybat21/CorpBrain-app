# [보고서] RN-CMD-02 승인된 Diff 기반 OS 레벨 물리 파일 Rename 및 내역 확정 구현 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issue #38 실시간 갱신 완료)

---

## 1. 구현 개요 (`RN-CMD-02` & `RN-CMD-03`)

본 태스크는 SRS `REQ-FUNC-018` 및 `GRILL_LEDGER.md` (DEC-03, DEC-05, DEC-08) 규격에 준수하여, 승인된 추천 파일명 Diff를 OS 물리 파일 시스템에 적용(`os.rename`)하고 SQLite DB 상태를 확정(Applied) 및 원복(Undo)하는 모듈을 구축한 구현 건입니다.

### 🔑 주요 핵심 반영 사안
1. **OS 레벨 물리 파일 변경 (`os.rename`) 및 트랜잭션 격리 (`DEC-05`)**:
   - 디스크 변경 중단 시 DB와 파일 경로가 어긋나는 것을 방지하기 위해 **파일 1개 OS 변경 성공 시 즉시 `File_Meta` 커밋**.
2. **딥링크 앵커 및 최초 원본 불변성 보장 (`DEC-08`)**:
   - 파일 변경 시 **`File_Meta.current_path`·`file_name`만 UPDATE**.
   - **`original_path`는 절대 변경하지 않으며(최초 스캔 시점 불변), `Wiki_Content.markdown_content` 및 `deeplink_mappings`도 전혀 손대지 않음**.
3. **부분 실패 격리 (HTTP 207 Multi-Status, `DEC-03`)**:
   - 파일 권한 부족 또는 파일 미존재/잠금 시 해당 항목만 `failed[]` 배열로 수집하여 HTTP 207 응답.
4. **원복(Undo) 메커니즘 연동 (`RN-CMD-03`)**:
   - `Rename_History.old_paths`/`new_paths` 기록을 기반으로 옛 물리 경로 및 `current_path`로 100% 되돌리는 `undo_rename()` 완비.
5. **IPC REST API 엔드포인트 수립**:
   - `POST /api/v1/workspace/{workspace_id}/rename/apply`
   - `POST /api/v1/workspace/{workspace_id}/rename/undo`

---

## 2. 검증 결과 (`tests/test_rn_cmd_02.py`)

- **Pytest 실행 결과**: **총 54개 전체 자동화 테스트 100% 통과** (실행시간: 6.51초)
  - `test_scenario_1_apply_rename_executes_os_rename_and_updates_file_meta`: OS rename 및 `original_path` 불변성 검증.
  - `test_scenario_2_rename_does_not_break_deeplinks_or_wiki_contents`: 위키 딥링크 앵커 `[[file_id:name]]` 파괴 방지 검증 (`DEC-08`).
  - `test_scenario_3_apply_rename_partial_failure_isolation`: 1개 미존재 파일 실패 시 HTTP 207 Multi-Status 격리 검증.
  - `test_scenario_4_undo_rename_reverts_physical_file_and_meta`: `undo_rename()` 호출 시 물리 파일 및 DB metadata 100% 원복 검증.
