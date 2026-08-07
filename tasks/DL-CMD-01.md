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
- **확정 사항: `DEC-08`** — 앵커 형식은 `[[file_id:<UUID>]]` 단일안, 경로는 위키에 저장하지 않음(late binding)

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 마크다운 내 앵커 패턴 **`[[file_id:<UUID>]]`** 파싱 로직 구현 (이 형식이 유일한 앵커 규격이며 대안 형식을 병기하지 않는다)
- [ ] 추출된 식별자를 DB의 `File_Meta`와 조인하여 유효성 확인
- [ ] `Wiki_Content.deeplink_mappings`에 **문장 인덱스 → `file_id`** 만 저장한다. **절대 경로·파일명을 함께 캐시하지 않는다** (`DEC-08`)
- [ ] LLM 위키 생성 프롬프트/후처리에서 출처 표기가 경로가 아닌 `file_id` 앵커로 나오도록 보장 (경로가 본문에 유입되면 즉시 stale 딥링크가 된다)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 유효한 딥링크 생성
- Given: `[[file_id:UUID_1]]` 태그가 포함된 위키 본문이 주어짐
- When: 딥링크 매핑 함수를 실행함
- Then: 정상적으로 파싱되어, 해당 파일 메타데이터와 관계(Relation)가 맺어진다.

Scenario 2: 위키 본문·매핑에 경로 미포함 (DEC-08)
- Given: 위키가 생성되어 `deeplink_mappings`가 저장됨
- When: 저장된 `markdown_content`와 `deeplink_mappings` JSON을 검사함
- Then: **절대 경로 문자열(`C:\` 등)이 단 하나도 포함되지 않으며**, 매핑 값은 전부 `file_id` UUID다.

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-03
- Blocks: DL-QRY-01
