---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-TEST-01: PII 마스킹 단위 테스트 및 마스킹 실패 예외 검증"
labels: 'test, backend, priority:high, security'
assignees: ''
---

## :dart: Summary
- 목적: PII 마스킹 파이프라인이 **정규식 7종**을 정확히 탐지·치환하고, **무결성 2조건 판정**이 부분 치환 버그까지 잡아내며, 실패 시 외부 전송을 차단하는지(Fail-Safe) 검증한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-008, 009`, `REQ-NF-006`
- **확정 사항: `DEC-14`** — 정규식 7종 / `[PII:TYPE]` 토큰 / 무결성 2조건 AND / fail-closed / 로그 위생

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **7종 각각의 Edge case 데이터셋 구성 (`DEC-14`)**: 주민등록번호, 전화번호(휴대/유선/국번 없는 형태), 이메일, 계좌번호, 신용카드번호, 사업자등록번호, 여권번호. 하이픈 유무·공백 구분자·전각 문자 변형을 포함한다
- [ ] PII 필터 통과 후의 텍스트가 **`[PII:TYPE]` 기대값과 100% 일치**하는지 단위 테스트 단언(Assert). `[MASKED]`·별표 형식은 실패로 처리한다
- [ ] **조건ⓐ와 조건ⓑ를 각각 독립적으로 실패시키는 테스트를 분리 작성한다 (`DEC-14`)**: ⓐ만 통과하는 부분 치환 케이스, ⓑ만 통과하는 신규 패턴 생성 케이스 — 2조건 AND가 실제로 필요한 근거를 테스트가 증명해야 한다
- [ ] **중첩 매치 병합 테스트**: 두 패턴이 겹치는 문자열에서 토큰이 중복 삽입되거나 오프셋이 밀리지 않는지 검증
- [ ] 정규식 엔진 에러 등으로 치환 실패(Mocking) 발생 시 외부 API 요청이 차단되는지 방어망 테스트 (**fail-closed** — 예외 시 통과 경로가 없음을 단언)
- [ ] **ReDoS 회귀 테스트**: 병리적 입력(반복 구분자 등)에 대해 각 패턴의 매칭 시간이 상한 내에 끝나는지 검증
- [ ] **로그 위생 테스트 (`DEC-14`)**: 마스킹 성공·실패 양쪽 경로에서 로그 출력과 `MaskedResult`에 원본 PII 문자열이 없고 타입별 건수만 있는지 단언

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 마스킹 로직 단위 테스트 통과 (DEC-14)
- Given: "010-1234-5678", "test@test.com", "990101-1234567" 문자열이 주어짐
- When: 마스킹 함수를 실행함
- Then: 각각 **`[PII:PHONE]`, `[PII:EMAIL]`, `[PII:RRN]`** 으로 치환되고, 원본 숫자·자릿수 정보가 결과에 남지 않은 것을 검증한다.

Scenario 2: 조건ⓐ 단독으로는 통과하는 부분 치환 케이스 차단 (DEC-14)
- Given: 주민번호의 앞 6자리만 치환되어 뒷자리가 남은 마스킹 결과가 주어짐 (재스캔 시 매치 0건)
- When: `validate_integrity()`를 실행함
- Then: 조건ⓑ 위반으로 **False**가 반환되어 전송이 차단된다.

Scenario 3: NER 미도입 검증 (DEC-14 / DEC-06)
- Given: 인명("김철수")과 기관명이 포함된 청크가 주어짐
- When: 마스킹 함수를 실행함
- Then: 인명은 **치환되지 않은 상태로 통과**하며(정규식 범위 외), `_ner_scan()`이 빈 리스트를 반환함을 단언한다. 이는 결함이 아니라 `DEC-14`가 명시한 범위이며, 미탐 고지 UX로 보완된다.

## :construction: Dependencies & Blockers
- Depends on: LLM-CMD-02
