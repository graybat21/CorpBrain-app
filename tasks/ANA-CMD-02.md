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

## :link: References (Spec & Context)
- **확정 사항: `DEC-06`** — ChromaDB + Ollama `nomic-embed-text`(768차원)
- **확정 사항: `DEC-09`** — chunk ID는 `<file_id>:<chunk_index>`, `vector_ids` 컬럼 미사용, `delete → upsert` 순서 고정
- **확정 사항: `DEC-16`** — 임베딩 호출 실패는 일시적 오류만 3회 재시도 후 **해당 파일만 실패 처리하고 다음 파일로 진행**

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 포맷별 텍스트 추출 어댑터 구현 (`python-docx` / `pdfminer.six` — SRS §8 승인 목록 내에서만 사용)
- [ ] 문단/구문 단위로 텍스트 분할(Chunking) 알고리즘 적용 (예: 500 토큰 단위, Overlap 50 설정)
- [ ] 텍스트 청크를 임베딩하고 `VectorDBManager.upsert_file_chunks(file_id, chunks)`로 저장 (FAISS 미사용)
- [ ] 저장 전 **`delete_file(file_id)` 선행 호출** — 재분석 시 잉여 chunk 잔존 방지 (`DEC-09`)
- [ ] **`File_Meta`에 chunk ID를 기록하지 않는다.** 벡터 작업 완료 후 `parse_status='parsed'`만 짧게 커밋한다 (`DEC-09` 쓰기 순서)
- [ ] **파일 단위 실패 격리 (`DEC-16`)**: 파싱·임베딩 실패 시 재시도(일시적 오류 한정 3회) 소진 후 해당 파일의 `parse_status`를 `parsed`로 올리지 않고 `Async_Task` 실패 목록에 `file_id`·`error.code`를 누적한 뒤 **다음 파일로 계속 진행**한다. 원문 청크는 실패 기록에 담지 않는다
- [ ] **연속 실패 상한 (`DEC-16`)**: 연속 10건 실패 시 남은 파일을 처리하지 않고 `status='failed'` + `LLM_UNAVAILABLE`로 작업을 종료한다 (데몬이 내려간 상태에서 전체 파일을 각각 재시도하지 않는다)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: PDF 문서 추출 및 벡터 DB 삽입
- Given: 텍스트가 포함된 유효한 3페이지 짜리 PDF 파일이 주어짐
- When: 심층 파싱을 지시함
- Then: 텍스트가 추출되고 설정된 청크 크기 단위로 쪼개져 벡터 DB 스토리지에 총 N개의 레코드로 저장된다.

Scenario 2: 손상 파일 1건이 작업 전체를 중단시키지 않음 (DEC-16)
- Given: 10개 파일 중 1개가 임베딩 호출에서 반복 실패함
- When: 심층 분석을 실행함
- Then: 나머지 9개가 정상 저장되고, 실패 파일은 `parse_status != 'parsed'`로 남아 `data.failed[]`에 1건으로 보고되며 작업은 `completed`로 끝난다.

## :gear: Technical & Non-Functional Constraints
- 성능: 대용량 PDF 파싱 시 메모리 릭(Memory Leak) 방지를 위해 제너레이터 활용 및 스트리밍 파싱 적용
- 복구: 실패 파일은 `parse_status`가 `parsed`가 아니므로 재분석 시 자동으로만 재처리된다. **별도 재시도 큐를 만들지 않는다** (`DEC-16`)

## :construction: Dependencies & Blockers
- Depends on: DB-002, SCAN-CMD-01
- Blocks: ANA-CMD-03
