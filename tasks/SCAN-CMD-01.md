---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] SCAN-CMD-01: 파일 트리 순회 및 블랙리스트 제외 후 `File_Meta` 벌크 Insert"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [SCAN-CMD-01] 파일 트리 스캔 및 추출 (Command)
- 목적: 매핑된 워크스페이스의 실제 디렉토리를 순회하며 블랙리스트(`/node_modules`, `.git` 등)를 제외한 유효 파일(.md, .docx, .pdf, .txt)의 메타데이터를 추출해 DB에 벌크 저장한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-003, 005`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] OS 파일 시스템 순회 (재귀적 탐색) 로직 구현
- [ ] 확장자 화이트리스트 및 디렉토리 블랙리스트 필터링 구현
- [ ] 파일 메타(경로, 크기, 수정일 등)를 추출하여 `File_Meta` 테이블에 Bulk Insert (청크 단위로 DB I/O 최적화)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 블랙리스트 파일 필터링
- Given: `.git` 폴더와 `test.md`가 포함된 경로가 주어짐
- When: 파일 트리 스캔을 실행함
- Then: `.git` 안의 파일들은 완전히 무시되고 `test.md`의 메타데이터만 추출되어 반환/저장된다.

## :gear: Technical & Non-Functional Constraints
- 성능: 1,000개 파일 스캔 및 필터링 처리를 2초 이내에 완료 (비동기 IO 또는 스레드풀 활용 고려)

## :checkered_flag: Definition of Done (DoD)
- [ ] Bulk Insert를 통한 성능 최적화가 적용되었는가?

## :construction: Dependencies & Blockers
- Depends on: DB-001, WS-CMD-01
- Blocks: SCAN-CMD-02, SCAN-QRY-01
