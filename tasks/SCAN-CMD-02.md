---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] SCAN-CMD-02: 파일 수 10,000개 도달 시 순회 중단 및 Limit Guard 예외 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [SCAN-CMD-02] 스캔 Limit Guard (Command)
- 목적: 워크스페이스 내 파일이 10,000개를 초과할 경우 시스템 과부하를 막기 위해 즉시 스캔을 중단하고 예외를 발생시킨다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 순회 과정 중 누적 파일 수를 카운팅하는 로직 추가
- [ ] Count가 10,000 도달 시 즉시 Break하고 400 Bad Request(Payload Too Large) 커스텀 예외 반환

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Limit Guard 발동
- Given: 워크스페이스 내부에 10,005개의 유효 파일이 존재함
- When: 파일 스캔을 시작함
- Then: 10,000개를 만나는 순간 순회가 멈추고 파일 갯수 초과 에러 메시지가 리턴된다.

## :checkered_flag: Definition of Done (DoD)
- [ ] 10K Guard 테스트(SCAN-TEST-02) 작성 및 통과

## :construction: Dependencies & Blockers
- Depends on: SCAN-CMD-01
