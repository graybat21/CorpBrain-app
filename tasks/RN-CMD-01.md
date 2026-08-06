---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-CMD-01: LLM 템플릿 추천 호출 및 Diff 결과를 DB에 임시 저장"
labels: 'feature, backend, priority:high, llm'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-CMD-01] 파일명 추천 Diff 생성 (Command)
- 목적: 파일 메타와 컨텍스트를 LLM에 전달하여 일관된 규칙의 파일명 추천안을 받고, 기존 이름과 새 이름이 매핑된 Diff 상태를 임시로 DB에 저장한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `REQ-FUNC-016`, `REQ-NF-006`
- DTO 명세: `API-003`
- **확정 사항: `DEC-17`** — Rename 프롬프트도 `DEC-14`의 `PIIFilter`를 **그대로 재사용**하고, **절대 경로를 전송하지 않는다**(파일명·확장자·1-depth 폴더명·뎁스만)
- **확정 사항: `DEC-16`** — LLM 호출 실패는 일시적 오류만 3회 재시도 후 해당 파일만 추천 제외
- **확정 사항: `DEC-15`** — 클라우드 호출은 `NetworkGuard`(`purpose='llm_cloud'`) 경유

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **프롬프트 컨텍스트 구성 (`DEC-17`)**: `_build_prompt_context()`는 **파일명 + 확장자 + 1-depth 폴더명 + 뎁스 수치**만 담는다. `File_Meta.current_path`·`original_path`의 전체 문자열, 드라이브 문자, `C:\Users\<계정명>`, UNC 서버명을 **프롬프트에 넣지 않는다**
- [ ] **마스킹 게이트 재사용 (`DEC-17`)**: Option A로 나가는 프롬프트는 `DEC-14`의 `PIIFilter.mask()` + `validate_integrity()`를 그대로 통과시킨다. **Rename 전용 마스킹 로직·전용 토큰 형식·전용 예외 처리를 새로 만들지 않는다.** "청크인지 파일명인지"로 분기하지 않는다 — 분기가 곧 우회 지점이다
- [ ] 마스킹·검증 실패는 **fail-closed**로 전송 차단(`PII_MASKING_FAILED`). 로그에는 타입별 건수만 남기고 원본 파일명을 남기지 않는다 (`DEC-14`)
- [ ] LLM(Option A/B) 호출 및 JSON Array 형태의 결과(원래 이름, 제안된 이름) 수신/파싱. 클라우드 호출은 `NetworkGuard`(`purpose='llm_cloud'`) 경유 (`DEC-15`)
- [ ] **응답에 `[PII:TYPE]` 토큰이 잔존하면 파일명으로 사용하지 않는다 (`DEC-17`)**: 해당 파일을 추천 대상에서 제외하고 Diff 목록에 "PII 포함 — 수동 확인 필요"로 표시한다. **원본 PII를 되살리는 역치환(un-masking)은 금지**
- [ ] **Windows 파일명 안전성 검증 (`DEC-17`)**: 금지 문자(`\ / : * ? " < > |`)·예약어(`CON`, `PRN`, `NUL`, `COM1`…)·후행 공백·마침표를 거부하고 `MAX_PATH`(260자) 초과를 사전 차단한다 (REQ-NF-007)
- [ ] 수신된 Diff 매핑 데이터를 `Rename_History` 혹은 임시 테이블에 `status='pending'` 상태로 Insert
- [ ] 호출 실패 파일은 추천 대상에서 제외하고 **원래 이름을 유지**한다 (`DEC-16` 부분 실패 규칙)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 올바른 Diff 포맷 수신
- Given: 무작위 이름의 파일 3개가 주어짐
- When: Rename 추천을 요청함
- Then: 3개 파일에 대한 규칙적인 네이밍 제안이 담긴 매핑 리스트가 임시 상태로 DB에 저장된다.

Scenario 2: PII 포함 파일명 마스킹 후 전송 (DEC-17)
- Given: `홍길동_주민등록증_900101-1234567.pdf`가 Option A 환경에서 추천 대상에 포함됨
- When: Rename 추천을 요청하고 전송 페이로드를 캡처함
- Then: 페이로드에 `900101-1234567`이 존재하지 않고 `[PII:RRN]`으로 치환되어 있으며, **절대 경로 문자열도 존재하지 않는다.**

Scenario 3: 토큰 잔존 응답의 파일명 사용 거부 (DEC-17)
- Given: LLM이 `[PII:RRN]_신분증.pdf`처럼 토큰이 남은 이름을 반환함
- When: Diff 목록을 생성함
- Then: 해당 파일은 추천에서 제외되고 **"PII 포함 — 수동 확인 필요"** 로 표시되며, 원본 주민번호를 되살린 이름은 생성되지 않는다.

## :gear: Technical & Non-Functional Constraints
- 보안: `REQ-NF-006`은 심층 분석 청크와 **Rename 프롬프트를 모두 포함**한다 (`DEC-17`). 검증 TC는 TC-SEC-005
- 경로 위생: 프롬프트·로그·에러 응답 어디에도 절대 경로를 남기지 않는다 (`DEC-08`과 동일 원칙)

## :construction: Dependencies & Blockers
- Depends on: API-003, LLM-CMD-01, LLM-CMD-02(PIIFilter), INF-CMD-03(NetworkGuard)
- Blocks: RN-QRY-01
