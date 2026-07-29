---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-CMD-01: Watcher 설정 모드(수동/실시간/유휴) 변경 및 DB 저장"
labels: 'feature, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-CMD-01] Watcher 동작 모드 관리 (Command)
- 목적: 파일 변경 사항을 감지하는 Watcher 데몬의 동작 모드(Manual, Real-time, Idle, Off) 설정을 사용자가 변경하고, 이를 영구 저장소에 반영한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.6 → **REQ-FUNC-023** (Watcher Mode Config)
- DTO 명세: API-003
- 검증 TC: TC-WATCH-001

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Watcher Mode Enum 값(Manual, Real-time, Idle, Off) 정의
- [ ] 설정값 수신 시 `Watcher_Config` DB 테이블 갱신
- [ ] 갱신 즉시 백그라운드 Watcher 프로세스의 큐 처리 주기를 동적으로 변경하는 Pub/Sub 또는 시그널(Signal) 로직 연동

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 설정 변경 적용
- Given: 현재 Watcher 모드가 '수동(Manual)'임
- When: '실시간(Real-time)'으로 모드 변경을 요청함
- Then: DB에 설정이 반영되며, Watcher 데몬이 재시작되거나 큐 타이머가 즉시 활성화(0초)된다.

Scenario 2: 4개 모드 전환 및 영속화
- Given: Watcher 모드가 '실시간'임
- When: '유휴시간' 모드로 변경을 요청함
- Then: `Watcher_Config` DB에 저장되고 앱 재시작 후에도 '유휴시간'이 유지된다.

## :gear: Technical & Non-Functional Constraints
- 모드: Manual / Real-time / Idle / Off 4종 (REQ-FUNC-023)
- 자원: REQ-NF-002 — 모드 전환 시 데몬 CPU 스파이크 방지

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-WATCH-001 통과
- [ ] WA-CMD-02 Signal/Pub-Sub 연동 확인

## :construction: Dependencies & Blockers
- Depends on: DB-001
- Blocks: WA-CMD-02
