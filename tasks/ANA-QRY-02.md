---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-QRY-02: 분석 진행 상태(Progress) 산출 및 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-QRY-02] 분석 Progress Query
- 목적: 비동기로 진행되는 파싱 및 LLM 생성 태스크의 현재 진행 현황(처리 수, 전체 수, ETA)을 API로 제공한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.3 → **REQ-FUNC-015** (Analysis Progress Indicator)
- API 명세: API-002

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 처리 중인 파일 수 / 전체 스캔 파일 수 비례 계산 로직 작성 (메모리 큐 또는 DB 트래킹)
- [ ] ETA 산출 및 Progress DTO 직렬화 API(Query) 구현
- [ ] `GET /api/v1/analyze/{task_id}/progress` 엔드포인트 연동

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 진행률 DTO 반환
- Given: 분석 태스크 ID `task-abc`가 45/200 파일 처리 중
- When: `GET /api/v1/analyze/task-abc/progress`를 호출함
- Then: `{ processed: 45, total: 200, eta_seconds: 120, status: 'running' }` 형태로 반환된다.

Scenario 2: 존재하지 않는 태스크
- Given: 유효하지 않은 task_id가 주어짐
- When: Progress 조회를 요청함
- Then: 404 Not Found와 적절한 에러 메시지가 반환된다.

## :gear: Technical & Non-Functional Constraints
- 성능: 메모리 큐 또는 DB 트래킹으로 O(1) 진행률 조회
- 정확도: ETA는 WPM 250 기준 역산 (ASM-05)

## :checkered_flag: Definition of Done (DoD)
- [ ] ANA-FE-03 폴링 연동 스모크 테스트 통과
- [ ] Progress DTO가 API-002 명세와 일치

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-02, ANA-CMD-03
- Blocks: ANA-FE-03
