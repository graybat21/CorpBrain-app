---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-FE-01: 고속 분석 중요도 순 정렬 결과 리스트 렌더링"
labels: 'feature, frontend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-FE-01] 분석 결과 리스트 UI
- 목적: 분석 파이프라인에서 1차로 가공된(고속 분석) 파일들의 목록을 중요도(Score)가 높은 순으로 화면에 리스팅한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.3 → **REQ-FUNC-012** (Fast Analysis)
- API 명세: API-002, MOCK-002

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 파일명, 확장자, 경로, 중요도 배지를 포함하는 List Item 컴포넌트 개발
- [ ] 중요도 속성에 따른 내림차순 정렬 로직 구현
- [ ] Mock API를 연동하여 결과 리스트 렌더링 검증

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 중요도 순 정렬 리스트
- Given: 고속 분석 결과 '최종_기획서.docx'(score 85), '임시_메모.txt'(score 20)가 반환됨
- When: 분석 결과 패널을 렌더링함
- Then: 기획서가 상단에 하이라이트 배지와 함께 표시된다.

Scenario 2: 분석 전 Empty State
- Given: 고속 분석이 아직 실행되지 않음
- When: 결과 패널에 진입함
- Then: "고속 분석을 실행하세요" 안내와 실행 버튼이 표시된다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-012 — 0~100 점수 기반 시각적 하이라이트 (색상 그라데이션)
- 성능: 1,000건 리스트 가상 스크롤 적용

## :checkered_flag: Definition of Done (DoD)
- [ ] score 내림차순 정렬 단위 테스트
- [ ] MOCK-002 연동 E2E 스모크 테스트 통과

## :construction: Dependencies & Blockers
- Depends on: MOCK-002, ANA-CMD-01
- Blocks: ANA-FE-02
