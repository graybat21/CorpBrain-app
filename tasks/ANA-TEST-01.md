---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-TEST-01: 지원 4개 포맷 텍스트 추출 정확성 단위 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 목적: 파일 파싱 로직이 지원하는 4개 포맷(docx, pdf, txt, md)에 대해 정상적으로 텍스트를 추출하는지 검증한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-006`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 4가지 포맷의 Mock 파일(한글/영문 텍스트 포함)을 Test 리소스 디렉토리에 준비
- [ ] 파일 파서를 실행하고, 결과가 빈 문자열이 아니며 예상되는 텍스트를 포함하고 있는지 확인하는 Assert 작성
- [ ] 인코딩이 깨지거나 파일이 손상된 케이스(Edge case)에 대한 예외 처리 검증

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 4개 포맷 파싱 테스트
- Given: 지원되는 각 포맷의 테스트 파일 4개가 주어짐
- When: 파싱 파이프라인을 실행함
- Then: 4개의 파일 모두 정확히 텍스트가 추출되어 단위 테스트가 Pass된다.

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-02
