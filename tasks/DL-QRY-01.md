---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-QRY-01: 위키 내 딥링크 대상 원본 파일의 현재 존재(Broken) 여부 검증 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 목적: 위키에 표시될 파일이 현재 물리 디스크 상에서 지워졌거나 이동되었는지(Broken) 검증하고 결과를 반환한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `File_Meta`에 등록된 경로에 대해 `os.path.exists()` 런타임 체크 (Query)
- [ ] 유효한 딥링크는 `true`, 끊어진 링크는 `false`로 포함하여 응답

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 끊어진 딥링크 감지
- Given: 위키가 생성된 후 사용자가 OS 상에서 파일을 삭제함
- When: 위키 문서 조회를 수행함 (Query)
- Then: 반환되는 DTO에 해당 딥링크가 `is_broken: true` 상태로 전달된다.

## :construction: Dependencies & Blockers
- Depends on: DL-CMD-01
- Blocks: DL-FE-01
