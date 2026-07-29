---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-FE-01: UI 설정 콤보박스 및 상태 아이콘 렌더링"
labels: 'feature, frontend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-FE-01] Watcher 설정 UI
- 목적: 사용자가 Watcher 데몬의 구동 모드를 쉽게 확인하고 변경할 수 있도록 헤더나 설정 패널에 UI 요소를 렌더링한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.6 → **REQ-FUNC-023** (Watcher Mode Config)
- API: WA-QRY-01, WA-CMD-01

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 헤더 영역에 Watcher 상태(수동/실시간/유휴/끄기) 콤보박스 컴포넌트 마크업
- [ ] 현재 큐 대기건수를 뱃지(Badge) 형태로 표출
- [ ] 콤보박스 변경 시 `WA-CMD-01` API 통신 연동

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 모드 변경 콤보박스
- Given: 현재 Watcher 모드가 '수동'임
- When: 콤보박스에서 '실시간'을 선택함
- Then: WA-CMD-01 API가 호출되고 UI에 '실시간' 상태가 반영된다.

Scenario 2: 큐 대기 건수 뱃지
- Given: Watcher 큐에 5건이 대기 중
- When: 헤더 영역을 렌더링함
- Then: Watcher 아이콘 옆에 '5' 뱃지가 표시된다.

## :gear: Technical & Non-Functional Constraints
- UX: 4개 모드(수동/실시간/유휴/끄기) Enum 일치 (REQ-FUNC-023)
- 자원: REQ-NF-002 — 백그라운드 폴링 최소화

## :checkered_flag: Definition of Done (DoD)
- [ ] 모드 변경 성공/실패 Toast 피드백
- [ ] WA-QRY-01 폴링 연동 완료

## :construction: Dependencies & Blockers
- Depends on: WA-QRY-01, WA-CMD-01
- Blocks: WA-FE-02
