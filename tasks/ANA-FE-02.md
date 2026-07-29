---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-FE-02: 1-Depth 폴더별 위키 탭 분리 렌더링"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-FE-02] 위키 탭 UI
- 목적: 심층 분석으로 생성된 위키를 1-Depth 폴더별 독립 탭으로 분리 렌더링하여 맥락 혼선(Hallucination)을 방지한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.3 → **REQ-FUNC-013, 014** (Deep Analysis Wiki, Folder-Tab Separation)
- API 명세: ANA-QRY-01

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 1-Depth 폴더명을 탭 헤더로 하는 Tab 컴포넌트 구현
- [ ] 선택된 탭의 마크다운 본문 렌더링 (Remark/Rehype 파이프라인)
- [ ] ANA-QRY-01 API 연동 및 탭 전환 시 상태 보존

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 1-Depth 폴더별 탭 분리
- Given: '01_FE', '02_BE' 두 폴더의 위키가 생성됨
- When: 위키 뷰어를 렌더링함
- Then: 각 폴더가 독립 탭으로 표시되고 탭 간 내용이 혼합되지 않는다.

Scenario 2: 마크다운 렌더링
- Given: 위키 본문에 헤딩, 리스트, 코드블록이 포함됨
- When: 선택된 탭의 마크다운을 렌더링함
- Then: 서식이 깨지지 않고 딥링크 플레이스홀더가 보존된다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-014 — Hallucination 방지를 위한 탭 격리 필수
- 성능: 대용량 마크다운 Lazy 렌더링

## :checkered_flag: Definition of Done (DoD)
- [ ] 탭 전환 시 이전 탭 상태 보존
- [ ] DL-FE-01 딥링크 배지 슬롯 마운트 포인트 확보

## :construction: Dependencies & Blockers
- Depends on: ANA-QRY-01, APP-UI-01
- Blocks: DL-FE-01
