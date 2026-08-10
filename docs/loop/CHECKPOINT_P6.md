# CorpBrain Loop Checkpoint — P6 (열린 이슈 소진 + 출하 셸)

CORE: 0

MINOR: 1

## 의사결정 기록

| # | 분류 | 트랙/이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 1 | MINOR | T1 / #1 | 이슈 AC S2 의 "상위 3개 반환" 을 `GET /api/v1/workspace/{id}/file` 응답의 `top_ranked_file_ids: string[]` 필드로 노출하고, 상한 상수를 `FastAnalysisEngine.TOP_RANKED_LIMIT = 3` 으로 둔다. | SRS §6.1 API-002 는 `top_files` 를 `POST /analyze/fast` 응답에 두지만 `DEC-04` 가 그 응답을 `202 + task_id` 로 고정했으므로 노출 위치를 조회 엔드포인트로 옮겨야 한다. SRS §4.1.3 REQ-FUNC-012 는 "상위 문서" 라고만 쓰고 개수를 정하지 않으며, 숫자 3 은 이슈 #1 AC 에만 있다. 필드명·상수 배치는 세 문서에 근거가 없어 MINOR 로 계상. |
