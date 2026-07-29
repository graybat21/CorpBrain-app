---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-CMD-01: LLM 템플릿 추천 호출 및 Diff 결과를 DB에 임시 저장"
labels: 'feature, backend, priority:high, llm'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-CMD-01] 파일명 추천 Diff 생성 (Command)
- 목적: 파일 메타와 컨텍스트를 LLM에 전달하여 일관된 규칙의 파일명 추천안을 받고, 기존 이름과 새 이름이 매핑된 Diff 상태를 임시로 DB에 저장한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `REQ-FUNC-016`
- DTO 명세: `API-003`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 파일 메타데이터(현재 이름, 확장자, 뎁스) 기반 Rename 프롬프트 구성 로직 작성
- [ ] LLM(Option A/B) 호출 및 JSON Array 형태의 결과(원래 이름, 제안된 이름) 수신/파싱
- [ ] 수신된 Diff 매핑 데이터를 `Rename_History` 혹은 임시 테이블에 `status='pending'` 상태로 Insert

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 올바른 Diff 포맷 수신
- Given: 무작위 이름의 파일 3개가 주어짐
- When: Rename 추천을 요청함
- Then: 3개 파일에 대한 규칙적인 네이밍 제안이 담긴 매핑 리스트가 임시 상태로 DB에 저장된다.

## :construction: Dependencies & Blockers
- Depends on: API-003, LLM-CMD-01
- Blocks: RN-QRY-01
