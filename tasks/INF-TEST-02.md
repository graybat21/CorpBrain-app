---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] INF-TEST-02: 외부 클라우드(Telemetry) 통신 완전 격리 테스트"
labels: 'test, backend, priority:high, security'
assignees: ''
---

## :dart: Summary
- 목적: 기업 보안상 폐쇄망 동작이 보장되어야 하므로, **프로비저닝이 완료된 정상 상태(steady state)** 에서 LLM Option B 구동 중 어떠한 외부 분석(Telemetry) 트래픽도 발생하지 않음을 테스트 코드로 검증한다 (`DEC-13`).

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-005** (Telemetry Blocking)
- 제약: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §1.5.1 → **CON-03** (외부 Telemetry 원천 배제)
- 검증 TC: TC-SEC-002
- **확정 사항: `DEC-13`** — "오프라인"은 정상 상태의 속성이다. 허용되는 외부 통신은 **① Option A의 마스킹된 청크 전송, ② 프로비저닝 단계의 인스톨러·모델 바이너리 다운로드** 두 가지뿐이며, 세 번째 목적지 추가는 금지
- **확정 사항: `DEC-15`** — 강제 수단은 3층(`NetworkGuard` 관문 / CI import 린트 / 패킷 캡처)이며 **이 카드는 3층 전체를 검증**한다. 관련 요구사항 `REQ-NF-018`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **[1층] `NetworkGuard` 차단 단위 테스트 (`DEC-15`)**: 화이트리스트 외 호스트(`example.com` 등)를 각 `purpose`로 요청할 때 `EgressBlockedError`가 발생하고 **실제 소켓 연결이 만들어지지 않음**을 단언한다. 호스트 exact match 우회 시도(`api.anthropic.com.attacker.net`, `notapi.anthropic.com`)도 차단되는지 검증한다
- [ ] **[1층] `purpose`·목적지 쌍 불일치 차단 테스트**: `purpose='provisioning'`으로 Anthropic 엔드포인트를 호출하면 차단되는지 검증한다
- [ ] **[1층] 차단 로그 위생 테스트**: 차단 로그에 호스트와 `purpose`만 남고 요청 본문이 기록되지 않음을 단언한다
- [ ] **[2층] CI import 린트 규칙 검증**: `NetworkGuard` 구현 파일 외의 모듈에 `httpx`/`requests`/`socket`/`urllib.request` import를 삽입한 픽스처를 두고 린트가 **실패로 판정**하는지 확인한다 (규칙이 실제로 동작함을 증명하는 메타 테스트)
- [ ] **[3층]** 테스트 환경 구동 시 아웃바운드 HTTP/TCP 요청을 모니터링/인터셉트 하는 툴 세팅
- [ ] **[3층] 측정 시점을 프로비저닝 완료 이후로 고정한다 (`DEC-13`)**: Ollama와 필요 모델이 이미 준비된 상태에서 앱을 부팅해 측정한다. 온보딩 다운로드 트래픽을 위반으로 오판정하지 않는다
- [ ] **[3층]** 워크스페이스 스캔 및 로컬(Ollama) 위키 생성 파이프라인 전체 실행
- [ ] **[3층]** 실행 도중 `127.0.0.1`이나 내부 네트워크를 제외한 외부(인터넷)망으로의 요청이 단 1건이라도 잡히면 Fail 처리하는 Assertion 추가
- [ ] **[3층] Option A 송신 경로를 둘 다 순회한다 (`DEC-17`)**: 심층 분석 청크 전송과 Rename 추천 프롬프트 전송을 모두 발생시켜, 두 페이로드에 원문 PII와 절대 경로가 없음을 각각 단언한다. Rename을 "분석이 아니니까" 제외하지 않는다
- [ ] **[3층] 허용 목적지 화이트리스트를 테스트에 명시**한다: 정상 상태 Option B = `127.0.0.1`만. Option A = `127.0.0.1` + Anthropic 엔드포인트만. 그 외 목적지는 목적지명과 무관하게 Fail

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 정상 상태 완전 오프라인 검증
- Given: **Ollama와 필요 모델이 사전 준비된** Option B 앱 환경과 네트워크 요청 감지기가 켜져 있음
- When: 앱 내의 모든 기능(스캔, 심층 분석, 딥링크, Watcher, Rename)을 한 바퀴 순회함
- Then: 감지기 로그에 `127.0.0.1` 외 목적지 호출 기록이 전혀 없어야 하며 테스트가 성공한다.

Scenario 3: 폐쇄망에서 설치 시도 없음 검증 (DEC-13)
- Given: 인터넷이 차단되고 Ollama가 미설치인 환경
- When: `POST /api/v1/llm/onboard`를 호출함
- Then: 도달성 사전 확인 1회(HEAD) 이후 **인스톨러 다운로드 요청이 발생하지 않고** 작업이 `LLM_PROVISION_REQUIRED`로 종료되며, Anthropic 엔드포인트로의 폴백 호출도 잡히지 않는다.

Scenario 2: Option A의 모든 송신 경로에서 PII·절대 경로 미전송 확인
- Given: Option A 모드이며 PII 포함 문서가 **심층 분석**과 **Rename 추천** 두 경로 모두에서 처리됨
- When: 네트워크 패킷을 캡처함
- Then: 두 경로의 전송 페이로드 모두에 원문 PII가 없고 **`[PII:TYPE]` 타입 태그 치환만** 존재한다 (REQ-NF-006 / `DEC-14` / `DEC-17`). `***-****-****`처럼 자릿수를 남기는 형태가 나오면 실패다. 추가로 Rename 경로 페이로드에 드라이브 문자(`C:\`)·`Users\<계정명>`·UNC 접두사(`\\`)가 없어야 한다 (`DEC-17`).

Scenario 4: 화이트리스트 외 목적지 코드 레벨 차단 (DEC-15)
- Given: `NetworkGuard`가 초기화된 상태
- When: `purpose='llm_cloud'`로 `https://api.anthropic.com.attacker.net/v1/messages` 요청을 시도함
- Then: `EgressBlockedError`가 발생하고, 패킷 캡처에 **해당 호스트로의 DNS 조회·TCP 연결이 전혀 잡히지 않는다**.

Scenario 5: 관문 우회 코드가 CI에서 차단됨 (DEC-15)
- Given: `NetworkGuard` 외 모듈(`src/services/foo.py`)에 `import requests`가 추가된 픽스처
- When: CI 린트를 실행함
- Then: 린트가 **실패(non-zero exit)** 하며 위반 파일·라인이 보고된다.

## :gear: Technical & Non-Functional Constraints
- 보안: **정상 상태** Option B 시 외부망 요청 0건 (TC-SEC-002 — `DEC-13`)
- 보안: `NetworkGuard` 화이트리스트 강제 및 import 린트 동작 (TC-SEC-004 — `REQ-NF-018` / `DEC-15`)
- 테스트: HTTP/TCP 인터셉터 또는 Mock socket. 1·2층은 순수 단위/정적 테스트이므로 **네트워크 없이 CI에서 항상 실행**한다. 3층 패킷 캡처만 수동/야간 잡으로 분리 가능
- 제약: 1층 테스트는 `NetworkGuard`의 판정 로직을 검증하는 것이므로 실제 외부 요청을 발생시켜서는 안 된다

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-SEC-002 자동화 테스트 통과
- [ ] TC-SEC-004(1층 차단 단위 테스트 + 2층 린트 메타 테스트) 통과
- [ ] 보안 검토(A1 페르소나) 체크리스트 충족

## :construction: Dependencies & Blockers
- Depends on: API-003, LLM-CMD-01, **INF-CMD-03**(NetworkGuard 구현)
