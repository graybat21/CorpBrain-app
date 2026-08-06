---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-FE-02: 백그라운드 위키 갱신 성공 시 IPC Toast 알림 렌더링"
labels: 'feature, frontend, priority:low'
assignees: ''
---

## :dart: Summary
- 목적: 백그라운드 데몬에 의해 파일 재분석 및 위키 갱신이 완료되었을 때 시각적 알림(Toast)을 띄워 사용자에게 피드백을 제공한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.6 → **REQ-FUNC-025** (백그라운드 위키 갱신 알림)
- **확정 사항: `DEC-04`** — 서버→클라이언트 **푸시 채널은 존재하지 않는다**. 갱신 감지는 폴링 응답의 상태 변화로만 이루어지며 **WebSocket·SSE를 도입하지 않는다**

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **폴링 응답의 상태 변화(마지막 갱신 시각/`task_id` 완료)를 감지하는 리스너 구현** (`DEC-04`). 웹소켓 브로드캐스트 수신 방식은 채택하지 않는다
- [ ] 이벤트 수신 시 화면 우측 하단에 "위키가 최신화되었습니다" Toast UI 팝업 처리

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 실시간 갱신 알림 렌더링
- Given: 앱이 켜져 있고 실시간 동기화 모드가 켜져 있음
- When: 백그라운드에서 파일이 갱신되어 DB가 업데이트 완료됨
- Then: 프론트엔드 우측 하단에 성공 Toast 알림 UI가 팝업된다.

## :construction: Dependencies & Blockers
- Depends on: WA-CMD-03
