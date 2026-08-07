# CorpBrain Agentic Loop — Decision Log

> 이 파일은 에이전틱 루프 실행 중 PRD/SRS에 명시되지 않은 의사결정을 기록하는 체크포인트입니다.
> CORE 3건 또는 MINOR 10건 도달 시 루프가 즉시 종료됩니다.

CORE: 6
MINOR: 0

**STOP REASON: CORE_BUDGET_EXCEEDED (6/3)**
루프 `docs/goals/corpbrain-unblocked-batch.md` 는 2026-08-07 기준 공식 종료되었다.
아래 6건은 루프 실행 중 집계되지 않아 정지 장치가 작동하지 않았고, 사후 등재한 것이다.
성격상 "갈림길에서의 선택"이 아니라 **LOCKED 규격 미준수(재작업 항목)** 이므로,
해결은 이 로그가 아니라 재오픈된 이슈에서 추적한다.

## Decision Records

| # | Type | Issue | Decision | Rationale |
|---|------|-------|----------|-----------|
| 1 | CORE | #16 DB-002 | `VectorDBManager` 를 ChromaDB `PersistentClient` 대신 인메모리 `dict` 로 구현 (`src/backend/services/vector_service.py:19`) | DEC-06 위반. `chromadb` import·`ws_<id>` 컬렉션·`nomic-embed-text` 명시 주입 전무. 프로세스 종료 시 벡터 전량 소실 → 위키/검색 영속성 불성립 |
| 2 | CORE | #1 ANA-CMD-01, #44 SCAN-CMD-01 | `/api/v1/scan`·`/api/v1/analysis/fast` 를 `202`+`task_id` 없이 동기 실행 (`src/backend/api/app.py:108,120`) | DEC-04 위반. `Async_Task` 진행률 커밋·폴링 엔드포인트 부재 → REQ-NF-011 RPO/RTO 미충족, 중단 태스크 `interrupted` 전이 불가 |
| 3 | CORE | #32 LLM-QRY-01 | `LlmQueryService` 에서 `urllib.request` 직접 import 후 Ollama 호출 (`src/backend/services/query_services.py:168`) | DEC-15 위반. `NetworkGuard` 밖 네트워크 I/O는 CI 린트 차단 대상. 동시에 `validate_egress` 인자 순서 오류(:159,:161)로 실 가드 주입 시 100% 차단 |
| 4 | CORE | — (#14 APP-UI-01 범위 외) | pywebview 셸 없이 `npx vite preview` + 고정 포트로 앱 구동 (`run_app.py`) | DEC-01 위반. 출하 산출물에 Node 런타임 의존이 들어옴. PyInstaller `.spec`·`requirements.txt` 부재로 재현 가능한 빌드 자체가 없음 |
| 5 | CORE | — | 로컬 API 서버 포트 `8000` 및 세션 토큰 문자열 하드코딩 (`run_app.py`) | DEC-02 위반. 규격은 `port=0` OS 할당 + `secrets.token_urlsafe(32)`. 고정 토큰은 소스에 평문 상주 |
| 6 | CORE | — | FastAPI 전역 예외 핸들러 미구성 (`src/backend/api/app.py`, `@app.exception_handler` 0건) | DEC-03 위반. FastAPI 기본 `{"detail": ...}` 가 봉투 규격을 우회해 그대로 누출. 스택트레이스·절대경로 유출 경로가 열려 있음 |

## 해소 기록

| # | 상태 | 해소 커밋 / PR | 비고 |
|---|------|----------------|------|
| 1 | **RESOLVED** | `39f67de` (Phase 4) + `e9cd5b6` (Phase 5) — 이슈 #16 / PR | 인메모리 `dict` → `chromadb.PersistentClient`. `ws_<workspace_id>` 코사인 컬렉션, `OllamaEmbeddingFunction` 명시 주입(기본 ONNX EF 도달 불가를 테스트로 고정), DEC-09 삭제→upsert 순서·`f"{file_id}:{chunk_index}"` ID·lazy delete 구현. 배선 누락 2건(워크스페이스 삭제 시 벡터 정리 미실행, 파일 삭제 시 고아 벡터 잔존)도 함께 해소. 78 → 113 passed. **잔여**: AC S3 동의 UI/엔드포인트는 후속 이슈(강제·차단 로직은 완료), AC S2 실측은 이 PC 에 Ollama 미설치로 미수행 |
| 3 | **RESOLVED** | PR #86 (이슈 #32) | `urllib.request` 직접 import 제거 + `validate_egress` 인자 순서 수정 |

## 재발 방지 (다음 루프 적용 조건)

1. **구현 코드 변경이 0줄인 PR은 생성하지 않는다.** (Draft PR #73~#83 11건이 정확히 이 경로에서 나왔다 — 각 브랜치가 `main` 과 보고서 `.md` 1개만 다름)
2. **이슈 close 는 `scripts/github_task_tracker.py complete <TASK_ID>` 경로만 사용한다.** 임의 일괄 close 스크립트 금지 (`close_completed_issues.py` 의 번호↔태스크 라벨 오류로 이슈 상태가 역전되었다)
3. **LOCKED 결정(DEC-01~17) 위반은 발견 즉시 CORE 로 등재한다.** 위반을 "미완성"으로 분류해 카운터를 우회하지 않는다.
4. **목(mock)을 검증하는 테스트는 DoD 근거로 쓰지 않는다.** 목 주입 인자의 기본값이 실경로를 우회하면(예: `network_guard=None`, `mock_llm_callback`) 그 테스트는 규격을 검증하지 못한다.
