---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-TEST-01: Rename Undo 100% 원복 통합 테스트"
labels: 'test, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-TEST-01] Undo 무결성 테스트
- 목적: Batch Rename 실행 후 Undo 기능이 `Rename_History` DB를 기반으로 100% 원본 상태로 복구하는지 통합 테스트로 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.4 → **REQ-FUNC-019** (Undo Rename)
- 신뢰성: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-009** (Rename Rollback Integrity)
- 보안: §4.2 → **REQ-NF-006**(PII Pre-masking, Rename 프롬프트 포함 — `DEC-17`)
- 검증 TC: TC-REL-003, **TC-SEC-005**
- **확정 사항: `DEC-17`** — Rename 프롬프트도 동일 `PIIFilter` 게이트를 거치고 절대 경로를 전송하지 않는다

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 50개 파일 Batch Rename → Undo 시나리오 통합 테스트 작성
- [ ] Undo 중 파일 Lock으로 부분 실패 시 실패 목록 반환 검증
- [ ] Undo 후 물리 경로와 파일 해시값 일치 확인
- [ ] **Rename 프롬프트 PII 마스킹 검증 (`DEC-17` / TC-SEC-005)**: PII를 포함한 파일명 세트로 추천을 요청하고 전송 페이로드를 캡처해 **원본 PII 문자열이 0건**임을 단언한다
- [ ] **절대 경로 미전송 검증 (`DEC-17`)**: 페이로드에 드라이브 문자(`C:\`), `Users\<계정명>`, UNC 접두사(`\\`)가 존재하지 않음을 단언한다. 허용되는 것은 파일명·확장자·1-depth 폴더명·뎁스뿐이다
- [ ] **토큰 잔존 응답 처리 테스트 (`DEC-17`)**: `[PII:RRN]`이 남은 추천 이름을 Mock으로 반환시켜 해당 파일이 추천에서 제외되고 **역치환이 일어나지 않음**을 검증한다
- [ ] **Windows 파일명 안전성 테스트 (`DEC-17`)**: 금지 문자·예약어(`CON`, `NUL`)·후행 마침표·`MAX_PATH` 초과 추천이 모두 거부되는지 검증한다
- [ ] **전용 우회 경로 부재 검증**: `RenameManager`가 `PIIFilter`를 경유하지 않는 별도 전송 경로를 갖지 않음을 확인한다(Option A 경로에서 `PIIFilter.mask()` 호출 횟수 = 프롬프트 수)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 100% Undo 원복
- Given: 50개 파일이 Batch Rename으로 변경됨
- When: Undo 커맨드를 실행함
- Then: 모든 파일의 원본 경로와 이름이 100% 복원된다.

Scenario 2: 부분 실패 시 실패 목록 표시
- Given: Undo 중 2개 파일이 다른 프로세스에 의해 잠김
- When: Undo를 실행함
- Then: 48개는 원복되고 2개 실패 파일 목록이 반환된다.

Scenario 3: Rename 프롬프트에 원본 PII·절대 경로 부재 (DEC-17 / TC-SEC-005)
- Given: Option A 모드이며 `C:\Users\hong\기밀\홍길동_주민등록증_900101-1234567.pdf`가 추천 대상임
- When: Rename 추천을 요청하고 전송 페이로드를 캡처함
- Then: 페이로드에 `900101-1234567`과 `C:\Users\hong`이 **모두 존재하지 않고**, 파일명은 `[PII:RRN]`으로 치환된 형태로만 나타난다.

## :gear: Technical & Non-Functional Constraints
- 신뢰성: REQ-NF-009 — 50개 파일 기준 통합 테스트
- 보안: REQ-NF-006은 Rename 프롬프트를 포함한다 (`DEC-17`) — TC-SEC-005
- 트랜잭션: `Rename_History` 역순 조회 후 OS rename

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-REL-003 자동화 테스트 통과
- [ ] **TC-SEC-005**(Rename 프롬프트 PII·경로 미전송) 통과
- [ ] RN-CMD-03 DoD 연계 완료

## :construction: Dependencies & Blockers
- Depends on: RN-CMD-01, RN-CMD-02, RN-CMD-03
- Blocks: None
