---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-CMD-03: 청크 기반 LLM 위키 마크다운 생성 및 DB Insert"
labels: 'feature, backend, priority:high, llm'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-CMD-03] 위키 마크다운 생성
- 목적: 벡터 DB에 모인 컨텍스트를 바탕으로 1-Depth 최상위 폴더별로 LLM 프롬프트를 조합하여 체계화된 위키 문서를 작성하고 DB에 영속화한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 1-Depth 폴더를 기준으로 그룹화(Group-by)하여 관련된 청크 문맥(Context) 조회
- [ ] RAG 프롬프트 템플릿 구성 (요약, 추출 구조화 등)
- [ ] LLM(클라우드 또는 Ollama)에 문맥과 프롬프트를 전송하여 Markdown 결과 수신
- [ ] 수신된 Markdown 텍스트를 `Wiki_Content` 테이블에 Insert

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 정상 위키 문서 생성
- Given: 1-Depth 폴더 '01_Frontend'에 연관된 텍스트 청크들이 벡터 DB에 존재함
- When: 위키 생성 커맨드를 호출함
- Then: 프론트엔드 관련 내용만 요약된 마크다운 문서가 LLM을 통해 생성되고 DB에 저장된다.

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-02, LLM-CMD-01, LLM-CMD-02
