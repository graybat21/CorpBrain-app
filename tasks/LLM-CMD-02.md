---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-CMD-02: Option A 전송 전 PII 마스킹 인메모리 적용"
labels: 'feature, backend, priority:high, security'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-CMD-02] 개인정보(PII) 마스킹
- 목적: Option A(클라우드)를 사용할 경우, 외부로 전송되는 **모든 프롬프트**(심층 분석 청크 + Rename 추천 프롬프트)의 민감 정보를 전송 전에 **정규식으로 인메모리 치환**하고, **2조건 무결성 판정**을 통과한 것만 전송을 허용한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-008, 009`, `REQ-NF-006`
- **확정 사항: `DEC-14`** — 정규식 전용 7종 / 토큰 `[PII:TYPE]` / 무결성 2조건 AND 판정 / fail-closed / 로그 위생
- **확정 사항: `DEC-17`** — 이 모듈은 **Option A로 나가는 모든 프롬프트의 공용 게이트**다. Rename(`RN-CMD-01`)도 동일 인스턴스를 재사용하며, 호출자별 분기·전용 토큰 형식을 만들지 않는다

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **호출자에 무관한 단일 게이트로 설계한다 (`DEC-17`)**: `mask()`는 입력이 문서 청크인지 파일명인지 알지 못하며, 그 사실을 알아야 하는 분기를 만들지 않는다. `LLMRouter`가 Option A 경로의 **모든** 프롬프트에 이 게이트를 적용한다 — 분기가 곧 우회 지점이 된다
- [ ] **정규식 7종 모듈 작성 (`DEC-14`)**: 주민등록번호, 전화번호(휴대/유선), 이메일, 계좌번호, 신용카드번호, 사업자등록번호, 여권번호. 이 7종이 MVP 탐지 범위 전부다
- [ ] **`_ner_scan()`은 인터페이스만 정의하고 no-op으로 구현한다 (`DEC-14`)**. `spacy`·`transformers` 등 인프로세스 NER 모델을 추가하지 않는다 — `DEC-06`·CON-02 위반이다
- [ ] **치환 토큰은 `[PII:TYPE]` 형식** (`[PII:RRN]`, `[PII:PHONE]`, `[PII:EMAIL]`, `[PII:ACCOUNT]`, `[PII:CARD]`, `[PII:BIZNO]`, `[PII:PASSPORT]`). `[MASKED]`·`***-****-****`를 쓰지 않는다 (후자는 자릿수를 유출한다)
- [ ] **중첩 매치 병합**: 겹치는 매치는 넓은 범위 우선으로 병합하고, **문자열 뒤에서 앞 방향으로 치환**해 오프셋이 밀리지 않게 한다
- [ ] 텍스트 전처리 파이프라인(Interceptor) 구현 (인메모리에서만 치환하고 원본 DB나 파일은 수정 금지)
- [ ] **`validate_integrity()` 2조건 AND 판정 구현 (`DEC-14`)**: ⓐ마스킹 결과에 동일 정규식 세트 재적용 → 매치 0건, ⓑ탐지된 각 원본 매치 문자열이 결과에 substring으로 부재. **둘 다 참일 때만 True**를 반환한다
- [ ] **Fail-closed 로직**: 마스킹·검증 경로의 모든 예외를 구체 타입으로 포착해 `PII_MASKING_FAILED`(500)로 전송 차단한다. bare `except:` 금지, "검증 실패 시 통과" 경로 금지
- [ ] **로그 위생 (`DEC-14`)**: 매치된 원본 PII 문자열·원문 청크를 로그·에러 응답·`Analytics_Log`에 기록하지 않는다. `MaskedResult`는 **타입별 매치 건수**만 요약해 반환한다

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: PII 마스킹 및 타입 태그 치환 검증 (DEC-14)
- Given: Option A가 활성화되어 있고, "제 번호는 010-1234-5678 입니다." 라는 청크가 주어짐
- When: LLM API로 텍스트를 전송하기 직전 파이프라인을 통과함
- Then: 문자열이 **"제 번호는 [PII:PHONE] 입니다."** 로 치환되어 전송되며, 전송 페이로드에 원본 숫자와 **자릿수 정보가 남지 않는다.**

Scenario 2: 무결성 2조건 판정 — 부분 치환 버그 탐지 (DEC-14)
- Given: 치환 로직이 오프셋 오류로 주민번호 뒷자리 일부만 치환한 마스킹 결과가 주어짐
- When: `validate_integrity()`를 실행함
- Then: 조건ⓑ(원본 매치 문자열 substring 부재)가 실패하여 **전송이 차단**되고 `PII_MASKING_FAILED`가 반환된다. 조건ⓐ만으로는 통과할 수 있는 케이스임을 테스트가 명시한다.

Scenario 3: 로그에 원본 PII 미기록 검증 (DEC-14 / REQ-NF-006)
- Given: PII를 포함한 청크의 마스킹이 실패해 Fail-Safe가 발동함
- When: 로컬 로그 파일과 에러 응답 본문을 검사함
- Then: 원본 PII 문자열이 **어느 쪽에도 존재하지 않으며**, 로그에는 타입별 매치 건수만 남아 있다.

## :gear: Technical & Non-Functional Constraints
- 보안/성능: 원본 데이터가 영구 수정되지 않도록 얕은 복사/깊은 복사 주의. **모든 패턴에서 중첩 수량자를 배제**해 ReDoS를 방어하고, 사용자 입력으로 패턴을 조립하지 않는다
- **미탐 고지 (RSK-03 / `DEC-14`)**: 인명·기관명은 정규식으로 탐지되지 않는다. 이를 숨기지 않고 Option A 최초 전송 전 **마스킹 결과 미리보기와 명시적 동의**를 요구하며, 설정 화면에 미탐 범위를 고정 문구로 표시한다
- 마스킹은 **소켓 연결 이전**에 100% 완료되어야 한다 (REQ-NF-006). 검증 통과 이후에만 네트워크 계층을 호출한다

## :construction: Dependencies & Blockers
- Depends on: API-003
- Blocks: ANA-CMD-03
