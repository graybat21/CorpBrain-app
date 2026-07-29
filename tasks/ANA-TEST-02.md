---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-TEST-02: 위키 문서 격리(Isolation) 1-Depth 침범 검증 테스트"
labels: 'test, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 목적: 폴더별로 독립적인 컨텍스트를 가져야 하는 위키 생성 로직이, 다른 폴더의 벡터 데이터를 잘못 참조하지 않는지 검증한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-014`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `01_Frontend`와 `02_Backend` 폴더의 벡터 데이터가 각각 저장된 테스트용 Vector DB 세팅
- [ ] `01_Frontend`에 대한 위키 생성을 트리거
- [ ] 생성된 결과물 텍스트를 검사하여 `02_Backend` 전용 키워드가 포함되지 않았는지 단언(Assert)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 1-Depth 폴더 독립성 확인
- Given: 서로 완전히 다른 도메인의 텍스트가 두 폴더에 나누어져 있음
- When: 위키 생성 커맨드를 호출함
- Then: 각 폴더의 생성된 위키 결과물이 서로의 컨텍스트를 침범하지 않는다.

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-03, ANA-QRY-01
