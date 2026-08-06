---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] INF-CMD-03: NetworkGuard egress 단일 관문 및 import 금지 CI 린트"
labels: 'feature, backend, priority:high, security, infrastructure'
assignees: ''
---

## :dart: Summary
- 기능명: [INF-CMD-03] `NetworkGuard` — outbound 네트워크 egress 단일 관문
- 목적: CON-03·REQ-NF-005의 "Telemetry 원천 배제"를 **사후 패킷 캡처가 아니라 코드 구조로** 보장한다. 모든 외부 통신을 단일 모듈에 모으고, 허용 목적지를 코드 상수 화이트리스트로 고정하며, 관문 우회 코드가 머지되지 못하도록 CI 린트를 함께 도입한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.2 → **REQ-NF-005**(Telemetry Blocking), **REQ-NF-018**(Egress Whitelist Enforcement)
- 제약: §1.5.1 → **CON-03**(외부 Telemetry 원천 배제)
- **확정 사항: `DEC-15`** — 3층 방어(구조 / 정적 검사 / 동적 검증), `purpose` 태그 3종, 코드 상수 화이트리스트
- 연관 결정: `DEC-12`(Anthropic 단일), `DEC-13`(프로비저닝 2모드), `DEC-06`(Ollama 임베딩), `DEC-02`(로컬 API 서버는 inbound — 대상 아님)
- 검증 TC: TC-SEC-004 (구현 검증은 INF-TEST-02가 담당)

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **`NetworkGuard` 모듈 신설**: `request()` / `stream()` / `is_reachable()` 공개 API. 모든 시그니처의 **첫 인자는 `purpose`** 로 두어 태그 없는 호출이 문법적으로 불가능하게 한다
- [ ] **화이트리스트를 코드 상수로 정의 (`DEC-15`)**: `_ALLOWED: dict[str, frozenset[str]]` = `{'llm_local': {'127.0.0.1'}, 'llm_cloud': {'api.anthropic.com'}, 'provisioning': {<Ollama 배포 호스트>}}`. **`App_Config`·설정 파일·환경변수에서 읽지 않는다** — 런타임에 변경 가능한 화이트리스트는 화이트리스트가 아니다
- [ ] **호스트 exact match 판정**: `urllib.parse`로 파싱한 호스트를 소문자화해 `frozenset` 멤버십으로만 비교한다. `in`(부분 문자열)·`endswith`(접미사) 매칭 금지 — `api.anthropic.com.attacker.net` 우회 방지
- [ ] **`purpose`·목적지 쌍 검증**: `purpose`가 3종 중 하나가 아니거나, 목적지가 그 `purpose`의 집합에 없으면 차단한다. `purpose='provisioning'`으로 Anthropic을 호출하는 것도 차단 대상이다
- [ ] **`EgressBlockedError` 정의 및 fail-closed 처리**: 판정 실패 시 예외를 던지고 **요청 객체를 생성하지 않는다**(소켓 연결 개시 전 차단). 로그에는 차단된 호스트와 `purpose`만 남기고 **요청 본문·헤더는 기록하지 않는다**
- [ ] **기존 호출부를 전부 관문 경유로 교체**: `LLMRouter`(Anthropic·Ollama 생성), `VectorDBManager`(Ollama 임베딩), 프로비저닝 로직(`LLM-CMD-03`)이 직접 HTTP를 호출하지 않도록 정리한다. `anthropic` SDK는 SDK가 제공하는 커스텀 HTTP 클라이언트 주입 지점을 통해 관문을 경유시킨다
- [ ] **CI import 린트 규칙 추가 (`DEC-15` 2층)**: `NetworkGuard` 구현 파일을 제외한 모든 `src/**` 모듈에서 `httpx`·`requests`·`socket`·`urllib.request` import를 금지한다. `ruff`의 `flake8-tidy-imports` `banned-api` + per-file-ignores로 구성하고, 위반 시 CI가 non-zero로 종료되게 한다
- [ ] **예외 파일 목록 최소화**: 린트 예외는 `NetworkGuard` 구현 파일 **하나**만 허용한다. 예외를 추가하는 PR은 `DEC-15` 표 갱신을 동반해야 한다는 주석을 설정 파일에 남긴다
- [ ] **텔레메트리 SDK 부재 확인**: `requirements.txt`에 `sentry-sdk`·`posthog` 등 원격 리포팅 SDK가 없음을 확인하고, 크래시 정보는 로컬 롤링 로그(`INF-CMD-02`)에만 남기는 경로를 유지한다

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 허용 목적지 정상 통과
- Given: `NetworkGuard`가 초기화되고 로컬 Ollama가 구동 중임
- When: `purpose='llm_local'`로 `http://127.0.0.1:11434/api/embeddings`를 요청함
- Then: 요청이 정상 수행되고 응답이 반환된다.

Scenario 2: 화이트리스트 외 목적지 차단
- Given: `NetworkGuard`가 초기화됨
- When: `purpose='llm_cloud'`로 `https://api.anthropic.com.attacker.net/v1/messages`를 요청함
- Then: **`EgressBlockedError`가 발생**하고 해당 호스트로의 DNS 조회·TCP 연결이 일어나지 않으며, 로그에는 호스트와 `purpose`만 기록된다.

Scenario 3: 관문 우회 코드가 CI에서 차단됨
- Given: `src/services/` 아래 임의 모듈에 `import requests`가 추가됨
- When: CI 린트를 실행함
- Then: 린트가 **실패**하고 위반 파일·라인이 보고되어 머지가 차단된다.

## :gear: Technical & Non-Functional Constraints
- 보안: 허용 목적지는 `purpose`별 3종뿐이며 **네 번째 목적지 추가는 코드 변경이 아니라 설계 결정 변경**이다 — `DEC-15` 표와 `REQ-NF-005`를 같은 변경에서 함께 갱신하지 않은 추가는 거부한다
- 범위: `NetworkGuard`는 **outbound 전용**이다. `DEC-02`의 FastAPI 루프백 서버는 inbound이므로 대상이 아니다
- 금지: `socket.socket` 런타임 몽키패치로 우회를 막으려 하지 않는다 — ChromaDB·`anthropic` SDK 내부 소켓까지 가로채 PyInstaller 환경에서 재현 어려운 실패를 만들고, 2층 린트가 이미 같은 목적을 정적으로 달성한다
- 금지: `purpose='provisioning'` 요청의 본문·쿼리·User-Agent에 문서 정보(파일명·경로·내용)를 넣지 않는다
- 의존성: 신규 서드파티 추가 없음. HTTP 클라이언트는 기존 승인 스택(`httpx` — `anthropic` SDK 전이 의존성) 범위 내에서 사용한다

## :checkered_flag: Definition of Done (DoD)
- [ ] AC Scenario 1~3 전부 통과
- [ ] `src/**`에서 `NetworkGuard` 외 모듈의 네트워크 라이브러리 직접 import가 0건임을 린트로 확인
- [ ] INF-TEST-02(TC-SEC-002 / TC-SEC-004)가 이 모듈 위에서 통과

## :construction: Dependencies & Blockers
- Depends on: INF-CMD-02 (로컬 로깅)
- Blocks: LLM-CMD-01, LLM-CMD-03, DB-002, INF-TEST-02
