---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-QRY-01: 위키 내 딥링크 대상 원본 파일의 현재 존재(Broken) 여부 검증 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 목적: 위키에 표시될 파일이 현재 물리 디스크 상에서 지워졌거나 이동되었는지(Broken) 검증하고 결과를 반환한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-022`
- **확정 사항: `DEC-08`** — Broken = "DB에 `current_path`가 있으나 디스크에 실물 없음". 앱 내부 Rename은 broken을 만들지 않는다

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `deeplink_mappings`의 `file_id` 목록을 **한 번의 배치 조회**로 `File_Meta.current_path`로 해석 (앵커당 개별 쿼리 금지 — 위키 탭 열 때마다 N+1이 된다)
- [ ] 해석된 `current_path`에 대해 `pathlib.Path.exists()` 런타임 체크 (`original_path`를 검사하지 않는다)
- [ ] `file_id`가 `File_Meta`에 없는 경우(원문 레코드 삭제)도 `is_broken: true`로 처리
- [ ] 응답에는 `file_id` / `file_name` / `is_broken`만 담고 **절대 경로를 프론트로 내려보내지 않는다** (`DEC-03` 내부 경로 노출 금지, 열기는 DL-CMD-02가 `file_id`로 수행)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 끊어진 딥링크 감지
- Given: 위키가 생성된 후 사용자가 앱 외부(탐색기)에서 파일을 삭제함
- When: 위키 문서 조회를 수행함 (Query)
- Then: 반환되는 DTO에 해당 딥링크가 `is_broken: true` 상태로 전달된다.

Scenario 2: 앱 내부 Rename 후에도 딥링크 유지 (DEC-08)
- Given: 위키에 `[[file_id:UUID_1]]` 앵커가 존재하고, 해당 파일을 앱의 일괄 Rename으로 변경함
- When: 위키를 재생성하지 않고 그대로 조회함
- Then: 딥링크는 `is_broken: false`이며 `file_name`이 **변경된 새 이름**으로 반환된다.

## :construction: Dependencies & Blockers
- Depends on: DL-CMD-01
- Blocks: DL-FE-01
