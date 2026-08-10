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
| 2 | **RESOLVED** | 이슈 #8 ANA-QRY-02 / P2 | `TaskRepository`(Async_Task 전용 SQL) + `TaskRunner`/`TaskQueryService` 신설. `/scan`·`/analysis/fast`·`rename/apply`·`rename/undo` 4개 엔드포인트가 **`202`+`task_id` 만 반환**하고(동기 응답 폐기 — 사용자 확정), 진행률은 `GET /api/v1/analyze/{task_id}/progress` 폴링으로 받는다. 상태는 전부 `Async_Task` 행에 있으며 인메모리 dict 는 없다 — 별 `DatabaseManager` 로 같은 파일을 읽어 확인하는 테스트로 고정(dict 구현으로는 통과 불가). 진행률은 항목 단위 커밋(in-SQL 증분), 부팅 시 `running`·**`queued`** 좌초 행 → `interrupted` 전이 + 자동 재개 금지(`GET /api/v1/task/interrupted` 로 사용자에게 제시). 부분 실패는 `multi_status` 종료 상태 → `GET /api/v1/task/{id}/result` 가 **HTTP 207 + `data.failed[]`**(마이그레이션 `v002` 의 `result_json`; 202 응답이 실패 목록을 실을 수 없기 때문). 113 → 145 passed. **의도된 규격 이탈 1건**: ETA 를 이슈 본문의 "WPM 250 역산" 대신 태스크 자체 실측 처리율로 산출한다 — WPM 은 사람의 독서 속도이므로 파싱·추론 소요를 나타내지 못하고, 그것을 기계 ETA 로 표시하면 근거 없는 숫자가 된다. 외삽할 근거가 없으면 `eta_sec: null` 을 반환한다(SRS §6.2.8 은 NULLABLE) |
| 3 | **RESOLVED** | PR #86 (이슈 #32) | `urllib.request` 직접 import 제거 + `validate_egress` 인자 순서 수정 |
| 6 | **RESOLVED** | `37d97ab` (이슈 #91 / P4) | `_install_exception_handlers()` 3건 등재 — `StarletteHTTPException`(상태코드→DEC-03 코드 매핑, 5xx 는 `detail` 을 로그로 돌리고 응답에서 교체), `RequestValidationError`(Pydantic 오류를 `loc`+`msg` 로만 축약 — `errors()` 의 `input` 이 `POST /config/llm` 의 API 키를 응답에 되돌리는 것을 차단, DEC-12), `Exception`(트레이스백은 로컬 로그, 응답은 `INTERNAL_ERROR` 코드만 — `str(OSError)` 가 절대경로라서 DEC-03 위반이 된다). #90 관측 당시 누출됐던 원시 `{"detail": ...}` 와 평문 `Internal Server Error` 는 두 경로 모두 봉투로 정규화됐다. `tests/test_ws_fe_01.py` 가 4건으로 고정: 422 봉투+`field`, 키 미반향, 404 봉투, 500 에서 절대경로·`WinError`·`Traceback` 부재. **해소 계기**: 프론트 배선(#91)이 `error.code` 를 읽으므로, 봉투를 우회하는 응답은 UI 에서 전부 "알 수 없는 오류" 로 붕괴된다 |
| 4, 5 | **RESOLVED** | `b23a420` — PR #140 (이슈 #14) | 출하 셸이 실제로 조립됐다. `src/main.py`(pywebview 진입점) + `CorpBrain.spec`(PyInstaller `--onefile`) 신설. **CORE #4** — 위반 파일 `run_app.py` 는 리포에서 사라졌고, 그것을 대체할 준수 구현이 이번에 들어왔다. `npx vite preview` 경로 없음, Node 는 빌드 타임 도구로만 남고 산출물에 들어가지 않으며(spec `excludes` 에 `scripts.dev_serve` 포함), `COLLECT` 없이 단일 exe 를 만든다. SPA(`index.html`+`assets/`)와 migrations 7건 내장. **CORE #5** — 포트는 `port=0` OS 할당분을 바인딩된 소켓에서 되읽고, 토큰은 `create_app` 이 매 부팅 `secrets.token_urlsafe(32)` 로 생성한다. 하드코딩 0건이 뮤테이션으로 고정됐다 — 포트 `8000` 하드코딩·`0.0.0.0` 바인딩·헬스 게이트 무력화 각각에 대응 테스트가 실패한다. 부팅 순서도 DEC-02 그대로 서버 → `/api/v1/health` 확인 → 창이다. macOS 에서 `python -m PyInstaller --noconfirm CorpBrain.spec` exit 0, 패키징된 단일 바이너리가 **부팅→마이그레이션 적용→루프백 랜덤 포트 바인딩→헬스 200→정상 종료** 를 실제로 수행했고(`CorpBrain --check-only` exit 0), 롤링 로그에는 포트만 남고 세션 토큰은 남지 않았다. **잔여 — RESOLVED 판정에 포함되지 않는 미검증 범위**: Windows 호스트 미확보로 `CorpBrain.exe` 실행 스모크는 수행하지 못했다(실제 WebView2 렌더, 프레임리스 드래그, 런타임 부재 시 안내 다이얼로그, HashRouter 초기 라우트의 실동작). 전부 `docs/review/WINDOWS_SMOKE_CHECKLIST.md` §3.0 으로 이관했고 그 문서 §5 는 "한 항목도 수행되지 않음" 이다. 두 CORE 의 원문이 지적한 것("Node 런타임 의존", "재현 가능한 빌드 부재", "포트·토큰 하드코딩")은 Windows 실행 여부와 무관하게 해소됐으므로 RESOLVED 로 판정하되, 미검증 범위를 위와 같이 병기한다 |

## 루프 종료 후 수동 검증 (2026-08-07)

P2 착수 전 사용자 요청으로 `scripts/dev_serve.py` 를 띄워 22개 등록 라우트를 브라우저에서 직접 호출했다.
정상 확인: 인증 미들웨어(무토큰/오토큰 → `UNAUTHORIZED` 봉투), 워크스페이스 CRUD, 스캔·스캔 요약, fast 분석,
`POST rename/diff`(PII 게이트 + DEC-17 경로 위생), 딥링크 status/open, 워처 config/status, 애널리틱스 요약,
LLM config(`api_key_configured` 불리언만 노출 — DEC-12 준수), SPA `/`, Swagger `/docs`.
**P1 수정의 실경로 확증**: 워크스페이스 삭제 1회로 `%LocalAppData%\CorpBrain\vectors\` 에 `chroma.sqlite3` 가 생성됨
— `app.py` 가 vector_store 를 주입하지 않아 프로덕션에서 한 번도 도달하지 않던 경로다.

이 과정에서 테스트가 잡지 못한 결함 2건이 드러났다. 둘 다 **CORE 로 집계하지 않는다** — LOCKED 결정 위반이 아니라
미구현/미커버 범위이며, 종료된 루프의 카운터를 사후 조정하지 않는다는 전제를 유지한다(재발 방지 3의 취지는
"위반을 미완성으로 강등 금지"이지 그 역이 아니다).

| 발견 | 이슈 | 요지 |
|---|---|---|
| `GET /workspace/{id}/rename/diff` 가 100% 500 | #90 | `RenameQueryService.get_pending_rename_diff` 가 `Rename_History.status` 를 조회하나 해당 컬럼이 없다(`sqlite3.OperationalError`). 컬럼을 고쳐도 `old_paths`/`new_paths` 항목을 dict 로 읽는데 `RenameService` 는 문자열로 저장하므로 `AttributeError` 가 이어진다. **테스트 커버리지 0건**이라 113 passed 와 공존했다. 관측 중 CORE #6(전역 예외 핸들러 부재)도 재확인 — 원시 `{"detail": ...}` 와 평문 `Internal Server Error` 가 그대로 누출됐다 |
| `index.html` 이 Google Fonts CDN 을 로드 | #91 에서 해소 | `<link rel="preconnect">` 2건 + `<link rel="stylesheet">` 1건이 `fonts.googleapis.com`/`fonts.gstatic.com` 을 가리켰다. 이 파일은 PyInstaller `--add-data` 로 exe 에 박히므로 **출하 앱이 매 실행마다 호출하는 4번째 외부 목적지**였고, DEC-15 의 3개 쌍 화이트리스트에도 REQ-NF-005 에도 없다. NetworkGuard 를 경유하지 않으므로 가드로는 잡히지도 않는다. 폐쇄망에서는 도착하지 않을 폰트를 위해 첫 페인트 전 DNS 타임아웃을 지불했다. → 3개 태그 삭제, 타이포그래피는 Tailwind `font-sans`(OS UI 폰트)로 이관. `tests/test_ws_fe_01.py::test_index_html_references_no_external_origin` 이 소스와 **빌드 산출물 양쪽**에서 고정 — 소스가 깨끗한 것이 빌드가 깨끗함을 증명하지 않는다. CORE 로 등재하지 않는다: 종료된 루프의 카운터를 사후 조정하지 않는다는 전제(위 문단)를 동일하게 적용하며, 발견과 해소가 같은 PR 안에서 끝났다 |
| `src/frontend` 에 API 호출 0건 | #91 | `fetch(`/`axios`/`XMLHttpRequest`/`/api/v1` 문자열이 전무. 5개 페이지가 Zustand 초기값만 렌더링하므로 대시보드는 항상 0을 표시한다. 백엔드는 동작하고 UI 는 동작하나 **서로 만난 적이 없다** — 프론트 테스트가 없어 빌드도 통과한다 |

**교훈(재발 방지 5로 승격)**: 백엔드 단위 테스트 전량 그린은 "엔드포인트가 응답한다"를 뜻하지 않는다.
위 2건은 모두 코드를 읽어서가 아니라 **HTTP 로 한 번 호출해서** 드러났다.

## 재발 방지 (다음 루프 적용 조건)

1. **구현 코드 변경이 0줄인 PR은 생성하지 않는다.** (Draft PR #73~#83 11건이 정확히 이 경로에서 나왔다 — 각 브랜치가 `main` 과 보고서 `.md` 1개만 다름)
2. **이슈 close 는 `scripts/github_task_tracker.py complete <TASK_ID>` 경로만 사용한다.** 임의 일괄 close 스크립트 금지 (`close_completed_issues.py` 의 번호↔태스크 라벨 오류로 이슈 상태가 역전되었다)
3. **LOCKED 결정(DEC-01~17) 위반은 발견 즉시 CORE 로 등재한다.** 위반을 "미완성"으로 분류해 카운터를 우회하지 않는다.
4. **목(mock)을 검증하는 테스트는 DoD 근거로 쓰지 않는다.** 목 주입 인자의 기본값이 실경로를 우회하면(예: `network_guard=None`, `mock_llm_callback`) 그 테스트는 규격을 검증하지 못한다.
5. **엔드포인트를 추가·수정한 태스크는 `scripts/dev_serve.py` 로 실제 HTTP 호출 1회를 DoD 증거에 포함한다.** 단위 테스트 그린은 라우트가 응답한다는 뜻이 아니다 (#90, #91 이 정확히 이 공백에서 나왔다).
