---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] STAT-TEST-01: WPM 기반 절약 시간 산출 단위 테스트"
labels: 'test, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [STAT-TEST-01] WPM 통계 산출 테스트
- 목적: My Analytics의 '절약된 시간' 지표가 WPM 250 기준 공식으로 정확히 산출되는지 단위 테스트로 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.7 → **REQ-FUNC-027** (Time Saved Metric)
- 가정: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §1.5.2 → **ASM-05** (WPM 250)
- 검증 TC: TC-STAT-001

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] WPM 공식(단어 수 25,000 / 250 = 100분) 정확도 단위 테스트
- [ ] 분석 미완료 시 기본값(0) 반환 테스트
- [ ] 토큰/단어 비율 변환 규칙 경계값 테스트

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: WPM 절약 시간 계산
- Given: 총 추출 텍스트가 250,000 단어임
- When: STAT-QRY-01 통계 산출 로직을 실행함
- Then: 절약 시간이 1,000분(250,000 ÷ 250)으로 반환된다.

Scenario 2: 분석 미완료 시 기본값
- Given: 아직 분석이 한 번도 완료되지 않음
- When: 통계 Query를 호출함
- Then: 절약 시간 0, Empty State 플래그가 반환된다.

## :gear: Technical & Non-Functional Constraints
- 산출: `처리된 총 토큰 수 ÷ (250 WPM × 토큰/단어 비율)` (REQ-FUNC-027)
- 정밀도: 부동소수점 반올림 규칙 문서화

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-STAT-001 단위 테스트 통과
- [ ] STAT-FE-01 카드 위젯 연동 검증

## :construction: Dependencies & Blockers
- Depends on: STAT-QRY-01
- Blocks: None
