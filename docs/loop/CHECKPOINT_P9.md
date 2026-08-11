# CorpBrain Loop Checkpoint — P9 (워크스페이스 URL 버그 수정)

CORE: 0

MINOR: 1

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 1 | MINOR | #162 | 순수 URL 조립 로직을 신규 모듈 **`src/frontend/api/urlBuilder.ts`** 로 분리(`resolveApiUrl(baseUrl, locationHref, ...)`), `client.ts::buildUrl` 이 `window.location.href` 를 넘겨 위임. `window` 를 직접 읽지 않는 순수 함수라 회귀 테스트가 Node(`--experimental-strip-types`)로 **실제 코드를 그대로 실행**해 검증할 수 있다(신규 JS 테스트 러너 도입 없이 — 스모크 §1 준수). | 프론트엔드 파일 배치·모듈 분할은 PRD·SRS·CLAUDE.md 에 명시 없음(MINOR 예시의 "디렉터리 배치·테스트 픽스처 구조"). 신규 의존성 아님(파일 1개 추가). |
