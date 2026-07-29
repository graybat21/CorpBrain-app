---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] MOCK-002: 심층 분석 결과(폴더별 탭) 및 Rename Diff 반환 Mock 서버 세팅"
labels: 'feature, mock, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [MOCK-002] Analysis / Rename 도메인 Mock API 제공
- 목적: 분석 결과(위키 마크다운 내용) 및 파일명 변경 추천 결과(Diff) 화면을 개발하기 위한 Mock API 환경을 구축한다.

## :link: References (Spec & Context)
- API 명세: API-003

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 마크다운 더미 데이터가 포함된 WikiContent 응답 Mock 구현
- [ ] 구 파일명, 신규 파일명이 쌍으로 매핑된 Rename Diff Mock 구현
- [ ] 기존 Mock 서버 레지스트리에 새로운 엔드포인트 추가

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Rename Diff Mock 호출
- Given: Mock 서버가 활성화되어 있음
- When: `/api/v1/rename/diff`로 GET 요청을 보냄
- Then: `old_name`과 `new_name`이 매핑된 더미 리스트와 함께 200 OK를 반환한다.

## :gear: Technical & Non-Functional Constraints
- 포맷: 마크다운 텍스트는 이스케이프 처리가 제대로 되어 프론트엔드 뷰어 컴포넌트에서 렌더링 가능해야 함.

## :checkered_flag: Definition of Done (DoD)
- [ ] FE 연동 시 마크다운 및 Diff 테이블이 정상 렌더링되는 더미 데이터를 뿜어내는가?

## :construction: Dependencies & Blockers
- Depends on: API-003, MOCK-001
- Blocks: ANA-FE-01, ANA-FE-02, RN-FE-01, RN-FE-02
