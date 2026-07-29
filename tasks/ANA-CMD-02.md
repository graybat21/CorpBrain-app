---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-CMD-02: 문서 파싱 후 텍스트 청킹(Chunking) 및 벡터 DB Insert"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-CMD-02] 심층 분석 - 파싱 및 청킹
- 목적: 물리적 파일(docx, pdf, txt, md)을 열어 텍스트를 추출하고, LLM 처리 한계(Token)에 맞게 의미 단위 청크(Chunk)로 나눈 후 벡터 DB에 저장한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 포맷별 텍스트 추출 어댑터 구현 (`pdfplumber` 등 외부 라이브러리 연동)
- [ ] 문단/구문 단위로 텍스트 분할(Chunking) 알고리즘 적용 (예: 500 토큰 단위, Overlap 50 설정)
- [ ] 텍스트 청크를 임베딩(Embedding)하고 ChromaDB/FAISS에 Insert

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: PDF 문서 추출 및 벡터 DB 삽입
- Given: 텍스트가 포함된 유효한 3페이지 짜리 PDF 파일이 주어짐
- When: 심층 파싱을 지시함
- Then: 텍스트가 추출되고 설정된 청크 크기 단위로 쪼개져 벡터 DB 스토리지에 총 N개의 레코드로 저장된다.

## :gear: Technical & Non-Functional Constraints
- 성능: 대용량 PDF 파싱 시 메모리 릭(Memory Leak) 방지를 위해 제너레이터 활용 및 스트리밍 파싱 적용

## :construction: Dependencies & Blockers
- Depends on: DB-002, SCAN-CMD-01
- Blocks: ANA-CMD-03
