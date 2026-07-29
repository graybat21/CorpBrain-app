---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] STAT-QRY-01: WPM 기반 통계 산출"
labels: 'feature, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [STAT-QRY-01] 대시보드 통계 집계 (Query)
- 목적: 로깅된 액션과 추출된 문서량을 기반으로 '시간 절약(Time Saved)' 및 '압축률' 지표를 계산하여 프론트엔드로 반환한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-027, 029`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 총 추출 단어 수를 250 WPM 공식으로 나누어 '문서 읽는 데 절약한 시간' 도출 로직 구현
- [ ] "총 텍스트 토큰" 대비 "위키 토큰" 비율을 계산하여 압축률 산정
- [ ] 딥링크 클릭 수, 워처 갱신 수 SUM 쿼리 작성 및 DTO 반환

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 올바른 WPM 계산
- Given: 총 추출된 텍스트 볼륨이 250,000 단어임
- When: 대시보드 통계를 조회함
- Then: 절약된 시간 필드가 '1,000분' (혹은 환산된 시간)으로 반환된다.

## :construction: Dependencies & Blockers
- Depends on: STAT-CMD-01
- Blocks: STAT-FE-01
