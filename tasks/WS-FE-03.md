---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WS-FE-03: 대시보드 통계 바인딩 및 예외 수신 알림 다이얼로그 표시"
labels: 'feature, frontend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [WS-FE-03] 스캔 결과 대시보드 바인딩
- 목적: 스캔이 완료된 후 백엔드에서 넘겨주는 요약 정보(파일 수, 용량 등)를 화면에 표시하고, 10K 초과 등 시스템 에러 발생 시 사용자에게 친절하게 알린다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-003, 004`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 대시보드 상단의 '스캔된 파일 수', '예상 소요시간' 등 수치 영역 컴포넌트 데이터 바인딩 (Query 연동)
- [ ] 글로벌 에러 핸들링 로직(Axios Interceptor 등)에서 400 Bad Request 수신 시 모달창(또는 Toast) 표출 기능 추가
- [ ] 에러 팝업 시 이전 상태로 UI 원복하는 트랜지션 처리

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 10K 예외 모달 노출
- Given: 새 워크스페이스 추가 시 OS 폴더에 10,000개가 넘는 파일이 있음
- When: 추가 버튼을 클릭함
- Then: 서버에서 반환된 400 에러를 캐치하여 사용자에게 "파일이 너무 많습니다" 에러 다이얼로그를 띄우고 생성 상태를 초기화한다.

## :construction: Dependencies & Blockers
- Depends on: APP-UI-01, MOCK-001
