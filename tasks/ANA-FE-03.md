---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-FE-03: 분석 진행률 프로그레스 바 렌더링"
labels: 'feature, frontend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-FE-03] 분석 Progress UI
- 목적: 고속/심층 분석 진행 중 처리된 파일 수 / 전체 파일 수 비율을 프로그레스 바로 실시간 표시한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.3 → **REQ-FUNC-015** (Analysis Progress Indicator)
- API: `GET /api/v1/analyze/{task_id}/progress`
- **확정 사항: `DEC-04`** — 진행률은 **1초 주기 폴링**으로만 얻는다. **WebSocket·SSE를 도입하지 않는다** (푸시 채널은 설계상 존재하지 않음)

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] **1초 주기 Progress API 폴링(Polling) 로직 구현** (`DEC-04`). SSE·WebSocket 구독 방식은 채택하지 않는다
- [ ] `처리 완료 N / 전체 M` 프로그레스 바 및 잔여 ETA 표시 컴포넌트
- [ ] 분석 완료 시 프로그레스 바 100% 전환 및 완료 모달 표시

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 프로그레스 바 실시간 갱신
- Given: 심층 분석이 진행 중이며 30/100 파일 처리 완료
- When: 1초 주기 Progress API를 폴링함
- Then: `30 / 100` 프로그레스 바와 잔여 ETA가 UI에 표시된다.

Scenario 2: 분석 완료 전환
- Given: 100/100 파일 처리 완료
- When: Progress API가 `status: completed`를 반환함
- Then: 프로그레스 바가 100%로 전환되고 완료 모달이 표시된다.

## :gear: Technical & Non-Functional Constraints
- UX: 폴링 간격 **1초** (`DEC-04`), 완료 시 폴링 중단
- 성능: REQ-NF-003 — 100파일 300초 이내 완료 시 ETA 정확도 ±10%

## :checkered_flag: Definition of Done (DoD)
- [ ] 폴링 중 메모리 릭 없음 (완료·언마운트 시 타이머 해제)
- [ ] SSE·WebSocket 클라이언트 코드가 존재하지 않음 (`DEC-04`)
- [ ] ANA-QRY-02 백엔드 API 연동 완료

## :construction: Dependencies & Blockers
- Depends on: ANA-QRY-02
- Blocks: None
