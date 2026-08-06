---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-FE-01: Rename Diff 미리보기 테이블 렌더링"
labels: 'feature, frontend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-FE-01] Rename Diff UI
- 목적: AI가 추천한 파일명 변경 전/후 Diff를 시각적 테이블로 렌더링하여 사용자 승인을 받는다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.4 → **REQ-FUNC-017** (Rename Diff Preview)
- API: RN-QRY-01
- **확정 사항: `DEC-17`** — PII 토큰이 잔존한 추천은 파일명으로 쓰지 않고 **"PII 포함 — 수동 확인 필요"** 상태로 표시된다

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Before(빨강) / After(초록) 2열 Diff 테이블 컴포넌트 개발
- [ ] 개별/전체 승인·거부 체크박스 및 [선택 적용] 버튼 구현
- [ ] RN-QRY-01 API 연동 및 확장자 유지 시각 확인
- [ ] **PII 수동 확인 행 렌더링 (`DEC-17`)**: 추천이 제외된 파일은 After 열에 제안 대신 **"PII 포함 — 수동 확인 필요"** 배지를 표시하고 승인 체크박스를 비활성화한다. 사용자가 직접 이름을 입력할 수 있는 인라인 편집만 허용한다
- [ ] **추천 실패 행 표시 (`DEC-16`)**: LLM 호출 실패로 추천을 받지 못한 파일은 "추천 실패 — 원래 이름 유지"로 표시한다. 실패를 화면에서 감추지 않는다

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Diff 미리보기 테이블
- Given: 5건의 Rename Pending Diff가 존재함
- When: Diff 미리보기 화면을 렌더링함
- Then: 기존 이름(빨강)과 신규 이름(초록)이 나란히 5행 표시된다.

Scenario 3: PII 포함 파일의 승인 차단 (DEC-17)
- Given: 추천 응답에 `[PII:TYPE]` 토큰이 남아 제외된 파일 1건이 포함됨
- When: Diff 테이블을 렌더링함
- Then: 해당 행은 **"PII 포함 — 수동 확인 필요"** 로 표시되고 일괄 승인에 포함되지 않으며, 사용자가 직접 입력하지 않는 한 이름이 바뀌지 않는다.

Scenario 2: 개별 승인/거부
- Given: 3건 중 1건을 사용자가 거부 체크함
- When: [선택 적용] 버튼을 클릭함
- Then: 승인된 2건만 Apply API에 전달된다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-017 — 확장자 유지 시각 확인
- 무결성: REQ-NF-009 — Undo 가능 상태 UI 표시

## :checkered_flag: Definition of Done (DoD)
- [ ] Before/After 색상 대비 WCAG AA 준수
- [ ] RN-QRY-01 API 연동 완료

## :construction: Dependencies & Blockers
- Depends on: RN-QRY-01
- Blocks: RN-FE-02
