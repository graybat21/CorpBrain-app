---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-CMD-02: Option A 전송 전 PII 마스킹 인메모리 적용"
labels: 'feature, backend, priority:high, security'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-CMD-02] 개인정보(PII) 마스킹
- 목적: Option A(클라우드)를 사용할 경우, 추출된 텍스트에 포함된 민감 정보(주민번호, 전화번호, 이메일 등)를 외부로 전송하기 전에 정규식을 이용해 인메모리 상에서 치환(마스킹)한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-008, 009`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 이메일, 전화번호, 주민등록번호 등을 필터링하는 정규표현식(Regex) 모듈 작성
- [ ] 텍스트 전처리 파이프라인(Interceptor) 구현 (인메모리에서만 치환하고 원본 DB나 파일은 수정 금지)
- [ ] 예기치 않은 오류 발생 시 외부 전송 원천 차단(Fail-Safe) 로직 구현

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: PII 마스킹 및 전송 차단 검증
- Given: Option A가 활성화되어 있고, "제 번호는 010-1234-5678 입니다." 라는 청크가 주어짐
- When: LLM API로 텍스트를 전송하기 직전 파이프라인을 통과함
- Then: 문자열이 "제 번호는 ***-****-**** 입니다." 로 치환되어 클라우드에 전송된다.

## :gear: Technical & Non-Functional Constraints
- 보안/성능: 원본 데이터가 영구 수정되지 않도록 얕은 복사/깊은 복사 주의. 정규식 백트래킹 취약점(ReDoS) 대비.

## :construction: Dependencies & Blockers
- Depends on: API-003
- Blocks: ANA-CMD-03
