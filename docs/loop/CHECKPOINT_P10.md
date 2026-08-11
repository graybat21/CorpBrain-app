# CorpBrain Loop Checkpoint — P10 (네이티브 폴더 선택기)

CORE: 1

MINOR: 0

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 1 | CORE | #167 | **pywebview `js_api` 브리지 도입** — REST(DEC-02/DEC-03) 밖의 인프로세스 IPC 채널을 신설해 SPA 가 네이티브 폴더 다이얼로그를 호출하게 함(`ShellApi.select_folder` → `create_file_dialog(FileDialog.FOLDER)`). 브라우저 JS 는 OS 폴더 선택기를 직접 못 열어 이 기전이 불가피. **범위를 UI 다이얼로그 트리거로 한정** — 문서·파일 내용은 여전히 Bearer-게이트 REST 로만 흐른다. js_api 는 포트 없는 인프로세스 브리지라 WebView 자기 페이지만 호출 가능(HTTP 루프백보다 오히려 격리적)이라 DEC-02/DEC-03 위반은 아님. dev_serve/브라우저에는 `window.pywebview` 가 없어 모달이 수동 입력으로 우아하게 degradation. | SRS §"다중 폴더 선택" 은 기능은 명세하나 그 *기전*(js_api/native dialog)은 PRD·SRS·CLAUDE.md 어디에도 없다. DEC-02/DEC-03 은 IPC 를 토큰-게이트 REST 로 규정하며 제2 채널을 언급하지 않는다 → REST 밖 신규 IPC 채널 도입은 규칙 2-2 의 CORE 항목("REST 밖 신규 IPC 채널")에 정확히 해당해 CORE 등재. |
