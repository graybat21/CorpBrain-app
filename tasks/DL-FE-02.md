---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-FE-02: 딥링크 onClick 시 브라우저 기본 동작 차단 및 IPC(Command) 호출"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 목적: 위키 내의 딥링크 버튼을 클릭할 때 발생하는 웹 브라우저의 기본 링크 이동 동작을 막고, IPC(또는 로컬 서버 API)로 요청을 우회 전송한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 딥링크 배지 Button 컴포넌트에 onClick 이벤트 바인딩
- [ ] `e.preventDefault()` 및 `e.stopPropagation()` 적용
- [ ] 백엔드 `DL-CMD-02` 엔드포인트 호출 및 에러(권한 없음, 파일 없음) 수신 시 Toast UI 렌더링

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 딥링크 클릭 차단
- Given: 정상적인 딥링크 배지가 렌더링됨
- When: 사용자가 배지를 마우스로 클릭함
- Then: 브라우저가 새 탭을 열지 않고 백엔드 API 단으로 요청(Command)을 보낸다.

## :construction: Dependencies & Blockers
- Depends on: DL-CMD-02, DL-FE-01
