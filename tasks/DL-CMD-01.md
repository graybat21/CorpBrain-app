---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] DL-CMD-01: 위키 문장과 `File_Meta` 간 매핑(Anchor) 식별자 DB Update"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [DL-CMD-01] 딥링크 식별자 매핑 (Command)
- 목적: LLM이 생성한 위키 마크다운 내부의 인용구(출처)와 실제 로컬 시스템 상의 `File_Meta`를 연결하는 고유 식별자(Anchor)를 삽입/저장한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `REQ-FUNC-020`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 마크다운 내 특정 패턴(예: `[[file_id:123]]`) 파싱 로직 구현
- [ ] 추출된 식별자를 DB의 `File_Meta`와 조인하여 유효성 확인
- [ ] 식별자 매핑 정보를 DB에 최종 확정

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 유효한 딥링크 생성
- Given: `[[file_id:UUID_1]]` 태그가 포함된 위키 본문이 주어짐
- When: 딥링크 매핑 함수를 실행함
- Then: 정상적으로 파싱되어, 해당 파일 메타데이터와 관계(Relation)가 맺어진다.

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-03
- Blocks: DL-QRY-01
