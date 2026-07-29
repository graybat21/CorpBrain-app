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

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] IPC(또는 로컬 HTTP 서버) 커맨드 수신 라우터 구현
- [ ] 수신된 파일 ID 기반 물리 경로(Path) 조회
- [ ] Windows API(`os.startfile()` 또는 `subprocess.Popen`)를 호출하여 애플리케이션 실행

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 외부 문서 오픈
- Given: 바탕화면의 `test.docx` 경로가 매핑된 파일 ID가 주어짐
- When: IPC로 파일 열기 명령을 호출함
- Then: 백엔드에서 에러 없이 실행 함수가 호출되고 MS Word가 구동되어 파일이 열린다.

## :gear: Technical & Non-Functional Constraints
- 보안: 악의적인 경로(예: `cmd.exe`) 주입 차단을 위해, 사전에 스캔된 `File_Meta` 테이블 내의 화이트리스트 경로만 허용

## :construction: Dependencies & Blockers
- Depends on: API-003
- Blocks: DL-FE-02, STAT-CMD-01
