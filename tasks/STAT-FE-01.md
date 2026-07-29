---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] STAT-FE-01: My Analytics 차트 및 4대 지표 대시보드 UI 렌더링"
labels: 'feature, frontend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [STAT-FE-01] My Analytics UI
- 목적: 분석된 통계 지표(시간 절약, 팩트체크율, 압축률, 자동화 점수)를 게이미피케이션 요소가 포함된 직관적인 대시보드 UI로 렌더링한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.7 → **REQ-FUNC-027~030** (My Analytics 4대 지표)
- API: `GET /api/v1/analytics/summary`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 통계 DTO를 수신하여 4가지 주요 지표(카드 위젯 형태) 렌더링
- [ ] Recharts 등 경량 차트 라이브러리로 압축률 시각화
- [ ] 데이터 미존재(Empty State) 시의 기본 화면 구현

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 4대 지표 카드 렌더링
- Given: API에서 절약시간, 팩트체크율, 압축률, 자동화 점수가 반환됨
- When: My Analytics 페이지를 렌더링함
- Then: 4개 카드 위젯이 애니메이션과 함께 표시된다.

Scenario 2: Empty State
- Given: 분석 이력이 없어 모든 지표가 0
- When: My Analytics에 진입함
- Then: "분석을 시작하면 통계가 표시됩니다" Empty State가 노출된다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-028~030 게이미피케이션 문구 ("이번 주 N시간 절약", "N번의 팩트체크")
- 보안: REQ-NF-005 — 외부 Telemetry 전송 금지, 로컬 API만 사용

## :checkered_flag: Definition of Done (DoD)
- [ ] 4개 지표 각각 Empty/정상 상태 UI 구현
- [ ] STAT-QRY-01 API 연동 완료

## :construction: Dependencies & Blockers
- Depends on: STAT-QRY-01, API-003
- Blocks: None
