---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-CMD-03: 내용이 수정된 파일 재분석 및 위키 부분 재생성 후 DB 갱신"
labels: 'feature, backend, priority:high, llm'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-CMD-03] Watcher 기반 증분 분석 (Command)
- 목적: 큐에 적재된 수정된 파일들에 대해 해당 파일만 재파싱하고 관련된 1-Depth 폴더의 위키 마크다운을 부분적으로 갱신(Delta Update)한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-025`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 대상 파일의 기존 벡터(ChromaDB) 삭제 및 새 청크/임베딩 Insert (ANA-CMD-02 로직 재사용)
- [ ] 해당 파일이 속한 1-Depth 폴더 단위의 `Wiki_Content` 재생성 트리거 (ANA-CMD-03 로직 재사용)
- [ ] 재생성 성공 후 DB 갱신 및 프론트엔드로 알림 브로드캐스트

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 부분 재분석 트리거
- Given: `01_Backend` 폴더 내의 한 파일이 수정되어 큐에 들어옴
- When: 큐 프로세서가 작동함
- Then: `01_Backend` 영역의 위키 마크다운 문서만 재생성되어 DB에 업데이트된다.

## :construction: Dependencies & Blockers
- Depends on: WA-CMD-02, ANA-CMD-03
- Blocks: STAT-CMD-01, WA-FE-02
