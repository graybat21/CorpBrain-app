# [보고서] ANA-CMD-02 문서 파싱, 청킹 및 벡터 파이프라인 모듈 구현 및 검증 결과

- **작성 일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)
- **수명주기 상태**: **In Progress ➔ Done (Closed)** (GitHub Issue #3 실시간 갱신 완료)

---

## 1. 구현 개요 (`ANA-CMD-02`)

본 태스크는 `docs/grill/GRILL_LEDGER.md` (DEC-06, DEC-09, DEC-16) 및 SRS §8 규격에 준수하여 물리적 문서 파일(.docx, .pdf, .txt, .md)의 텍스트 파싱, 의미 단위 청킹(Chunking) 및 로컬 벡터 DB 파이프라인을 구축한 구현 건입니다.

### 🔑 주요 핵심 반영 사안
1. **다중 포맷 텍스트 파서 (`DocumentParser`)**:
   - `.docx` (`python-docx`), `.pdf` (`pdfminer.six` / `pypdf`), `.txt` / `.md` (인코딩 자동 감지 스트리밍 파싱).
2. **의미 단위 텍스트 청커 (`TextChunker`)**:
   - 500자/토큰 타겟 크기 및 50자 Overlap 기반 청킹 알고리즘.
   - Chunk ID 포맷: **`<file_id>:<chunk_index>`** 고정 (`DEC-09`).
3. **ChromaDB 벡터 파이프라인 규약 (`DEC-09`)**:
   - 재분석 시 잉여 chunk 잔존 방지를 위해 **`delete_file(file_id)`를 반드시 선행 호출 후 `upsert` 진행**.
   - `File_Meta` 테이블에 vector ID를 저장하지 않으며, 벡터 작업 완료 후 `parse_status='parsed'`만 커밋.
4. **파일 단위 부분 격리 및 서킷 브레이커 연동 (`DEC-16`)**:
   - `LLMResilienceService`와 연동하여 1개 파일 파싱/임베딩 실패 시 `failed[]` 수집 후 계속 진행, 10회 연속 실패 시 작업 중단.

---

## 2. 검증 결과 (`tests/test_ana_cmd_02.py`)

- **Pytest 실행 결과**: **총 50개 전체 자동화 테스트 100% 통과** (실행시간: 6.18초)
  - `test_scenario_1_deep_analysis_and_chunk_ids`: 텍스트 추출 및 `<file_id>:<chunk_index>` 앵커 포맷 검증.
  - `test_scenario_2_vector_delete_before_upsert_sequence`: 재분석 시 delete -> upsert 순서 및 잉여 청크 미발생 검증.
  - `test_scenario_3_batch_run_with_single_file_failure_isolation`: 1개 손상 파일 실패 시 격리 및 2개 정상 파일 `parsed` 전환 검증.
