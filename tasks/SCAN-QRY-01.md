---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] SCAN-QRY-01: 스캔된 파일 수, 용량(MB), 예상 소요시간 산출 후 반환"
labels: 'feature, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [SCAN-QRY-01] 스캔 요약 결과 제공 (Query)
- 목적: 파일 스캔 완료 후 총 갯수, 용량, 분석 예상 소요시간을 계산하여 프론트엔드 대시보드에 표시할 통계 DTO를 반환한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.1 → **REQ-FUNC-003** (Dashboard Scan Stats)
- DTO 명세: API-002
- 검증 TC: TC-WS-003

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `File_Meta`에서 워크스페이스 단위로 파일 개수 및 용량(SUM) 집계 (Query)
- [ ] WPM(Words Per Minute) 또는 평균 파일 크기 공식을 활용하여 ETA(예상 소요시간) 산출
- [ ] `ScanSummaryRes` DTO 구조로 반환

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 스캔 통계 DTO 반환
- Given: 워크스페이스 스캔이 완료되어 `File_Meta`에 120개 파일(총 48MB)이 저장됨
- When: `GET /api/v1/workspace/{id}/scan` 조회를 요청함
- Then: 파일 수(120), 총 용량(MB), 분석 예상 소요 시간(초)이 `ScanSummaryRes` DTO로 반환된다.

Scenario 2: 빈 워크스페이스 통계
- Given: 스캔 결과 유효 파일이 0건임
- When: 스캔 요약 조회를 요청함
- Then: count=0, size=0, eta=0으로 200 OK 응답이 반환된다.

## :gear: Technical & Non-Functional Constraints
- 성능: REQ-NF-001 — 통계 집계 포함 p95 < 5,000ms
- 산출: ASM-05 기준 WPM 250으로 ETA 계산

## :checkered_flag: Definition of Done (DoD)
- [ ] DTO 필드가 API-002 명세와 일치하는가?
- [ ] WS-FE-03 대시보드 연동 Mock 테스트 통과

## :construction: Dependencies & Blockers
- Depends on: SCAN-CMD-01
- Blocks: WS-FE-03
