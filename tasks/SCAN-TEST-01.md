---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] SCAN-TEST-01: 스캔 필터링(블랙리스트) 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [SCAN-TEST-01] 블랙리스트 필터링 단위 테스트
- 목적: 스캔 엔진의 필터링 규칙(블랙리스트 폴더, 허용 확장자만 스캔)이 SRS 명세대로 완벽히 동작하는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.1 → **REQ-FUNC-005** (Blacklist Folder Filter)
- 관련 태스크: SCAN-CMD-01
- 검증 TC: TC-WS-005

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 가상 파일 시스템(Mock FS)을 이용해 `.git`, `node_modules`, `Windows` 등 블랙리스트 폴더와 유효한 `.md` 파일을 혼합 생성
- [ ] SCAN-CMD-01 스캔 로직을 수행하고, 블랙리스트 경로 내 파일이 0건인지 단언(Assert)
- [ ] `.hwp`, `.xlsx` 등 미지원 확장자가 Skip되는지 별도 테스트 케이스 작성

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 블랙리스트 폴더 완전 제외
- Given: `.git`, `node_modules`, `Windows` 폴더와 유효한 `report.md` 파일이 혼재된 Mock FS가 주어짐
- When: SCAN-CMD-01 스캔 로직을 실행함
- Then: 블랙리스트 경로 내 파일은 0건이며, `report.md` 1건만 `File_Meta`에 저장된다.

Scenario 2: 미지원 확장자 필터링
- Given: `.docx`, `.hwp`, `.xlsx` 파일이 동일 폴더에 존재함
- When: 스캔을 실행함
- Then: `.docx`만 추출되고 `.hwp`, `.xlsx`는 Skip되며 로그에 기록된다.

## :gear: Technical & Non-Functional Constraints
- 성능: REQ-NF-001 기준 1,000개 파일 스캔 p95 < 5,000ms
- 안정성: REQ-NF-007 — 권한 거부 경로 Skip 시 테스트도 크래시 없이 완료

## :checkered_flag: Definition of Done (DoD)
- [ ] REQ-FUNC-005 AC를 충족하는 단위 테스트가 CI에서 통과하는가?
- [ ] Mock FS 기반 재현 가능한 테스트 픽스처가 문서화되었는가?

## :construction: Dependencies & Blockers
- Depends on: SCAN-CMD-01
- Blocks: SCAN-TEST-02
