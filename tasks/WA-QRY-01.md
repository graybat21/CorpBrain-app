---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-QRY-01: Watcher 상태 및 큐 대기 건수 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-QRY-01] Watcher 상태 조회 (Query)
- 목적: 현재 Watcher 구동 모드와 메모리 상 대기 큐 크기를 직렬화하여 프론트엔드에 반환한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.6 → **REQ-FUNC-023, 024** (Watcher Mode Config, Real-time Detection)
- API 명세: API-003

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 현재 구동 모드(수동/실시간/유휴/끄기)와 큐 대기 건수(N건) 직렬화 Query 구현
- [ ] Watcher 활성/비활성 상태 플래그 반환
- [ ] WA-FE-01 콤보박스 초기값 동기화용 DTO 정의

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Watcher 상태 조회
- Given: Watcher가 '실시간' 모드이며 큐에 3건 대기 중
- When: Watcher 상태 Query를 호출함
- Then: `{ mode: 'realtime', queue_size: 3, is_active: true }` DTO가 반환된다.

Scenario 2: Watcher 비활성 상태
- Given: Watcher 모드가 '끄기'로 설정됨
- When: 상태 Query를 호출함
- Then: `is_active: false`, `queue_size: 0`이 반환된다.

## :gear: Technical & Non-Functional Constraints
- 자원: REQ-NF-002 — 유휴 시 CPU < 1%, RAM < 100MB
- 실시간: REQ-FUNC-024 — 이벤트 감지 1초 이내

## :checkered_flag: Definition of Done (DoD)
- [ ] WA-FE-01 콤보박스 초기값 동기화
- [ ] API-003 DTO 명세 일치

## :construction: Dependencies & Blockers
- Depends on: WA-CMD-01, WA-CMD-02
- Blocks: WA-FE-01
