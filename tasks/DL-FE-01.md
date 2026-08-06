---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-FE-01: 위키 뷰어 내 딥링크 배지 렌더링 및 깨진 링크 시 회색/툴팁 처리"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [DL-FE-01] 딥링크 배지 UI
- 목적: 마크다운 렌더러에서 Trust-Anchor 딥링크 식별자를 인터랙티브한 배지(Badge) 버튼으로 시각화하고, Broken Link를 회색 처리한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.5 → **REQ-FUNC-020, 022** (Deep-link Generation, Broken Link Detection)
- API: DL-QRY-01

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 마크다운 파서 커스텀 플러그인(Remark 등)을 구현하여 `[[file_id:UUID]]` 식별자를 Button 컴포넌트로 치환
- [ ] DL-QRY-01 `is_broken` 플래그에 따라 회색 처리 및 Tooltip('원본 파일을 찾을 수 없습니다') 구현
- [ ] DL-FE-02 IPC 클릭 핸들러 슬롯 마운트 포인트 확보

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 딥링크 배지 렌더링
- Given: 위키 본문에 `[[file_id:UUID_1]]` 태그가 포함됨
- When: 마크다운 렌더러가 본문을 파싱함
- Then: 해당 위치에 클릭 가능한 딥링크 배지 아이콘이 표시된다.

Scenario 2: Broken Link 회색 처리
- Given: `UUID_1`에 매핑된 원본 파일이 OS에서 삭제됨
- When: 위키를 렌더링함
- Then: 배지가 회색 처리되고 "원본 파일을 찾을 수 없습니다" 툴팁이 표시된다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-022 — 비활성 링크 클릭 시 Toast 안내
- 렌더링: Remark/Rehype 커스텀 플러그인

## :checkered_flag: Definition of Done (DoD)
- [ ] DL-QRY-01 `is_broken` 플래그 연동
- [ ] DL-FE-02 IPC 클릭 핸들러 슬롯 준비

## :construction: Dependencies & Blockers
- Depends on: DL-QRY-01, ANA-FE-02
- Blocks: DL-FE-02
