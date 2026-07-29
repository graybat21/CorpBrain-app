---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] SCAN-TEST-02: 스캔 Limit Guard (10K 제한) 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [SCAN-TEST-02] Limit Guard 단위 테스트
- 목적: 스캔 엔진의 방어 기제인 10,000개 파일 수 제한(Limit Guard) 기능이 SRS 명세대로 초과 시 즉시 작동하는지 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.1 → **REQ-FUNC-004** (Scan File Limit Guard)
- 관련 태스크: SCAN-CMD-02
- 검증 TC: TC-WS-004

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 파일 10,001개를 생성하는 가상 파일 시스템(Mock FS) 구현 또는 Mock 객체를 통한 강제 카운트 설정
- [ ] 스캔 시도 시 Limit Guard 예외(또는 400 Payload Too Large)가 10,000개 시점에 발생하는지 검증
- [ ] 500개 이하 소규모 Mock FS에서 Limit Guard 미발동 정상 완료 케이스 추가

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 10,000개 도달 시 스캔 일시 정지
- Given: Mock FS에 유효 파일 10,005개가 존재함
- When: 파일 트리 스캔을 시작함
- Then: 10,000개 처리 시점에 순회가 중단되고 Limit Guard 예외(또는 400)가 반환된다.

Scenario 2: 10,000개 미만 정상 완료
- Given: Mock FS에 유효 파일 500개가 존재함
- When: 파일 트리 스캔을 시작함
- Then: Limit Guard가 발동하지 않고 500건 전체가 정상 저장된다.

## :gear: Technical & Non-Functional Constraints
- 확장성: REQ-NF-012 — 10,000개 파일 상한 방어 로직 검증
- UX: REQ-FUNC-004 — 초과 시 사용자 확인 다이얼로그 트리거 여부 연계 확인

## :checkered_flag: Definition of Done (DoD)
- [ ] 10,001개 Mock 환경에서 Limit Guard 단언(Assert) 통과
- [ ] SCAN-CMD-02 DoD 항목과 연계 완료

## :construction: Dependencies & Blockers
- Depends on: SCAN-CMD-02
- Blocks: WS-FE-03
