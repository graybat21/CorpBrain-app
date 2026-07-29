---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-TEST-01: PII 마스킹 단위 테스트 및 마스킹 실패 예외 검증"
labels: 'test, backend, priority:high, security'
assignees: ''
---

## :dart: Summary
- 목적: PII 마스킹 파이프라인 로직이 이메일, 전화번호 등의 개인정보를 완벽하게 감지하고 실패 시 외부 전송을 차단하는지(Fail-Safe) 검증한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 정규표현식(Regex)을 위한 다양한 포맷의 PII 더미 텍스트(Edge cases) 데이터셋 구성
- [ ] PII 필터 통과 후의 텍스트가 기대하는 마스킹 값과 100% 일치하는지 단위 테스트 단언(Assert)
- [ ] 정규식 엔진 에러 등으로 치환 실패(Mocking) 발생 시 외부 API 요청이 차단되는지 방어망 테스트

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 마스킹 로직 단위 테스트 통과
- Given: "010-1234-5678", "test@test.com", "990101-1234567" 문자열이 주어짐
- When: 마스킹 함수를 실행함
- Then: 모든 민감 정보가 별표(*)로 치환된 것을 검증한다.

## :construction: Dependencies & Blockers
- Depends on: LLM-CMD-02
