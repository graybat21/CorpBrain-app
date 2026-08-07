---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-CMD-02: IPC 기반 `os.startfile` 호출 로직 구현"
labels: 'feature, backend, priority:high, os'
assignees: ''
---

## :dart: Summary
- 기능명: [DL-CMD-02] 로컬 앱 열기 (Command)
- 목적: 프론트엔드에서 딥링크를 클릭했을 때 브라우저 샌드박스를 우회하여 IPC 통신을 통해 OS 기본 프로그램(워드, PDF 뷰어 등)으로 파일을 직접 연다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-021`
- DTO 명세: `API-003`
- **확정 사항: `DEC-08`** — 열기 대상 경로는 요청이 아니라 `file_id → File_Meta.current_path` 조회로 결정

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 로컬 HTTP 라우터 구현 (`DEC-02` Bearer 토큰 미들웨어 통과 필수)
- [ ] 요청 본문은 **`file_id`만 받는다.** 클라이언트가 보낸 경로 문자열을 신뢰하거나 수신하지 않는다 (경로 주입 차단 + `DEC-08` late binding)
- [ ] `file_id`로 `File_Meta.current_path`를 조회 (`original_path`를 열지 않는다 — rename 이후 존재하지 않는 경로다)
- [ ] Windows API(`os.startfile()`)를 호출하여 애플리케이션 실행. 실패 시 `NOT_FOUND`/`PATH_NOT_ACCESSIBLE` 에러 코드로 응답 (`DEC-03`)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 외부 문서 오픈
- Given: 바탕화면의 `test.docx` 경로가 매핑된 파일 ID가 주어짐
- When: IPC로 파일 열기 명령을 호출함
- Then: 백엔드에서 에러 없이 실행 함수가 호출되고 MS Word가 구동되어 파일이 열린다.

## :gear: Technical & Non-Functional Constraints
- 보안: 악의적인 경로(예: `cmd.exe`) 주입 차단을 위해, 사전에 스캔된 `File_Meta.current_path` 값만 허용한다. **API가 임의 경로를 파라미터로 받는 형태를 만들지 않는다** — `file_id` 조회 결과만 실행 대상이 된다.

## :construction: Dependencies & Blockers
- Depends on: API-003
- Blocks: DL-FE-02, STAT-CMD-01
