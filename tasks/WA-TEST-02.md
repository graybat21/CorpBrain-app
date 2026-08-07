---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-TEST-02: 유휴(Idle) 모드 Watcher 통합 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-TEST-02] Idle 모드 테스트
- 목적: '유휴시간' 모드에서 사용자 미입력 상태 진입 후에만 백그라운드 분석이 시작되고, 입력 재개 시 중단되는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.6 → **REQ-FUNC-026** (Idle-mode Watcher)
- 검증 TC: TC-WATCH-004
- 관련 태스크: WA-CMD-02

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 5분간 사용자 입력 없음 시뮬레이션 후 큐 일괄 Flush 검증
- [ ] 입력 재개 시 백그라운드 처리 일시 중단 검증
- [ ] 타이머 Mock 기반 재현 가능한 통합 테스트 작성

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 유휴 모드 일괄 처리
- Given: Watcher가 '유휴시간' 모드이며 5분간 사용자 입력 없음
- When: 누적 변경 이벤트 10건이 큐에 대기 중
- Then: 유휴 진입 후 10건이 일괄 Flush 처리된다.

Scenario 2: 입력 재개 시 처리 중단
- Given: 유휴 모드에서 큐 처리가 진행 중
- When: 사용자가 키보드 입력을 재개함
- Then: 백그라운드 처리가 일시 중단된다.

## :gear: Technical & Non-Functional Constraints
- UX: 기본 유휴 임계값 5분 (REQ-FUNC-026)
- 자원: REQ-NF-002 — 유휴 대기 중 CPU < 1%

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-WATCH-004 시뮬레이션 테스트 통과
- [ ] 타이머 Mock 기반 재현 가능

## :construction: Dependencies & Blockers
- Depends on: WA-CMD-02
- Blocks: None
