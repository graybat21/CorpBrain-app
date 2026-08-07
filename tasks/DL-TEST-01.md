---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-TEST-01: Broken Link 실시간 검증 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [DL-TEST-01] Broken Link 테스트
- 목적: 위키에 표시될 파일이 물리 디스크에서 삭제/이동되어 딥링크가 깨진 경우를 정확히 감지하는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.5 → **REQ-FUNC-022** (Broken Link Detection)
- 검증 TC: TC-DL-003
- 관련 태스크: DL-QRY-01

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 파일 삭제 시뮬레이션 후 `is_broken: true` 반환 검증
- [ ] 파일 이동 시뮬레이션 후 `os.path.exists()` 런타임 체크 검증
- [ ] Mock FS 기반 재현 가능한 테스트 픽스처 작성

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 파일 삭제 후 Broken 감지
- Given: 딥링크가 매핑된 파일이 존재함
- When: OS에서 해당 파일을 삭제하고 DL-QRY-01을 호출함
- Then: 응답 DTO에 `is_broken: true`가 포함된다.

Scenario 2: 파일 이동 후 Broken 감지
- Given: 딥링크가 매핑된 파일이 다른 경로로 이동됨
- When: `os.path.exists()` 런타임 체크를 수행함
- Then: `is_broken: true`가 반환되고 로그에 경로 불일치가 기록된다.

## :gear: Technical & Non-Functional Constraints
- 신뢰성: REQ-NF-007 — 파일 접근 예외 시 크래시 없이 false 반환
- 테스트: Mock FS로 삭제/이동 시뮬레이션

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-DL-003 자동화 테스트 통과
- [ ] DL-FE-01 Broken UI 연동 검증

## :construction: Dependencies & Blockers
- Depends on: DL-QRY-01
- Blocks: None
