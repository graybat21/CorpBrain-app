---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] INF-TEST-02: 외부 클라우드(Telemetry) 통신 완전 격리 테스트"
labels: 'test, backend, priority:high, security'
assignees: ''
---

## :dart: Summary
- 목적: 기업 보안상 폐쇄망 동작이 보장되어야 하므로, LLM Option B 구동 중일 때 어떠한 외부 분석(Telemetry) 트래픽도 발생하지 않음을 테스트 코드로 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-005** (Telemetry Blocking)
- 제약: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §1.5.1 → **CON-03** (외부 Telemetry 원천 배제)
- 검증 TC: TC-SEC-002

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 테스트 환경 구동 시 아웃바운드 HTTP/TCP 요청을 모니터링/인터셉트 하는 툴 세팅
- [ ] 워크스페이스 스캔 및 로컬(Ollama) 위키 생성 파이프라인 전체 실행
- [ ] 실행 도중 `127.0.0.1`이나 내부 네트워크를 제외한 외부(인터넷)망으로의 요청이 단 1건이라도 잡히면 Fail 처리하는 Assertion 추가

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 완전 오프라인 모드 검증
- Given: Option B로 설정된 앱 환경과 네트워크 요청 감지기가 켜져 있음
- When: 앱 내의 모든 기능(스캔, 딥링크, Watcher)을 한 바퀴 순회함
- Then: 감지기 로그에 외부망 호출 기록이 전혀 없어야 하며 테스트가 성공한다.

Scenario 2: Option A에서도 PII 미전송 확인
- Given: Option A 모드이며 PII 포함 문서가 분석됨
- When: 네트워크 패킷을 캡처함
- Then: 전송 페이로드에 원문 PII가 없고 `[MASKED]` 치환만 존재한다 (REQ-NF-006).

## :gear: Technical & Non-Functional Constraints
- 보안: Option B 시 외부망 요청 0건 (TC-SEC-002)
- 테스트: HTTP/TCP 인터셉터 또는 Mock socket

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-SEC-002 자동화 테스트 통과
- [ ] 보안 검토(A1 페르소나) 체크리스트 충족

## :construction: Dependencies & Blockers
- Depends on: API-003, LLM-CMD-01
