---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-TEST-01: Watcher 이벤트 디바운싱 및 필터링 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-TEST-01] 이벤트 필터링 테스트
- 목적: Watcher가 무의미한 중복 이벤트(단순 속성 변경)를 필터링하고 실제 내용 변경만 큐에 적재하는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.6 → **REQ-FUNC-024** (Real-time File Detection)
- 검증 TC: TC-WATCH-002
- 관련 태스크: WA-CMD-02

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 파일 속성만 변경(내용 동일) 시 이벤트 Skip 검증
- [ ] `.docx` 본문 수정 시 1초 이내 큐 적재 검증
- [ ] Mock watchdog 이벤트 시뮬레이션 픽스처 작성

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 단순 터치 이벤트 필터링
- Given: Watcher 옵저버가 실행 중이며 파일 내용 변경 없이 속성만 수정됨
- When: 디바운서(500ms) 및 타임스탬프 대조가 동작함
- Then: 이벤트가 Skip되고 큐에 적재되지 않는다.

Scenario 2: 실제 내용 변경 감지
- Given: `.docx` 파일 본문이 수정되어 `last_modified`가 변경됨
- When: OS Modified 이벤트가 발생함
- Then: 1초 이내 큐에 적재된다 (REQ-FUNC-024).

## :gear: Technical & Non-Functional Constraints
- 안정성: 무한 이벤트 루프 CPU 과점유 방지 (디바운싱 500~1000ms)
- 테스트: Mock watchdog 이벤트 시뮬레이션

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-WATCH-002 자동화 테스트 통과
- [ ] WA-CMD-02 DoD 연계 완료

## :construction: Dependencies & Blockers
- Depends on: WA-CMD-02
- Blocks: None
