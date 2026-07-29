---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] INF-TEST-01: 1,000개 파일 스캔 시 p95 < 5,000ms 성능 부하 테스트"
labels: 'test, backend, priority:medium, performance'
assignees: ''
---

## :dart: Summary
- 목적: 애플리케이션의 핵심 병목 구간인 '로컬 파일 스캔' 시, NFR 명세에 따른 응답 시간을 달성하는지 테스트 코드를 통해 자동 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-001** (Scan Latency p95 < 5s)
- 검증 TC: TC-PERF-001

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 1,000개의 더미 파일이 담긴 가상 디렉토리 생성 스크립트 작성
- [ ] 해당 디렉토리를 타겟으로 스캔 커맨드(API 혹은 함수) 호출 벤치마크 작성
- [ ] 실행 시간(Duration)을 측정하여 p95 기준 5,000ms를 초과하면 테스트를 실패(Fail)하도록 단언(Assert)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 스캔 성능 충족
- Given: 1,000개의 Mock 파일 트리
- When: 성능 테스트 스위트를 구동함
- Then: 5초(5000ms) 이내에 `File_Meta` Insert까지 모두 끝나고 테스트가 Pass된다.

Scenario 2: p95 초과 시 테스트 실패
- Given: 1,000개 Mock 파일 트리
- When: 스캔 벤치마크를 10회 반복 실행함
- Then: p95 응답 시간이 5,000ms를 초과하면 테스트가 Fail된다.

## :gear: Technical & Non-Functional Constraints
- 성능: REQ-NF-001 — UI Freezing 방지 목표
- 환경: CI에서 재현 가능한 Mock FS 필수

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-PERF-001 자동화 및 CI 통합
- [ ] SCAN-CMD-01 성능 회귀 감지 기준선(baseline) 문서화

## :construction: Dependencies & Blockers
- Depends on: SCAN-CMD-01
