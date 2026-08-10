# CorpBrain Loop Checkpoint — P6 (열린 이슈 소진 + 출하 셸)

CORE: 0

MINOR: 3

## 의사결정 기록

| # | 분류 | 트랙/이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 1 | MINOR | T1 / #1 | 이슈 AC S2 의 "상위 3개 반환" 을 `GET /api/v1/workspace/{id}/file` 응답의 `top_ranked_file_ids: string[]` 필드로 노출하고, 상한 상수를 `FastAnalysisEngine.TOP_RANKED_LIMIT = 3` 으로 둔다. | SRS §6.1 API-002 는 `top_files` 를 `POST /analyze/fast` 응답에 두지만 `DEC-04` 가 그 응답을 `202 + task_id` 로 고정했으므로 노출 위치를 조회 엔드포인트로 옮겨야 한다. SRS §4.1.3 REQ-FUNC-012 는 "상위 문서" 라고만 쓰고 개수를 정하지 않으며, 숫자 3 은 이슈 #1 AC 에만 있다. 필드명·상수 배치는 세 문서에 근거가 없어 MINOR 로 계상. |
| 2 | MINOR | T2 / #14 | HashRouter 를 `react-router-dom` 대신 **의존성 없는 자체 해시 라우터**(`src/frontend/router.ts`)로 구현한다. 라우트는 `#/dashboard` 등 6개 탭 + `#/workspace/<id>`. | 결과 자체는 세 문서가 결정한다 — CLAUDE.md §6·SRS §3.2 DEC-01 이 HashRouter 를 요구하고, CLAUDE.md §4 는 사전 승인 목록 밖 의존성 추가를 금지하는데 `react-router-dom` 은 목록에 없다. 따라서 CORE 가 아니다. 다만 자체 구현의 **모듈 배치·훅 이름·라우트 문자열**은 세 문서에 근거가 없어 MINOR 로 계상. |
| 3 | MINOR | T2 / #14 | DEC-02 의 "`/api/v1/health` 응답 확인 후 WebView 로드" 를 위해 `src/main.py` 에서 **stdlib `http.client`** 로 루프백 프로브를 수행하고, `ruff.toml` 의 banned-api 에 `http.client` 를 **추가**한 뒤 `src/main.py` 만 예외 처리한다. | DEC-15 의 금지 목록(`requests`/`socket`/`urllib.request`/`httpx`)에 `http.client` 가 없어 그대로 두면 **조용한 우회 통로**가 된다. DEC-15 는 NetworkGuard 를 outbound-external 전용으로 정의하고 루프백 인바운드 서버를 명시적으로 범위 밖에 두므로 위반이 아니다. 금지 목록에 추가 + 단일 파일 예외라는 **처리 방식**이 세 문서에 없어 MINOR 로 계상. |
