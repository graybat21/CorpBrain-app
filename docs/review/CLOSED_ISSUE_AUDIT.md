# CLOSED 이슈 코드 감사 (Closed Issue Audit)

**감사일**: 2026-08-07
**대상**: GitHub CLOSED 이슈 27건 + 적신호 확인 항목
**기준**: `tasks/<TASK-ID>.md` 의 Acceptance Criteria(GWT) + `.claude/CLAUDE.md` LOCKED 결정사항(DEC-01~17)
**방법**: 이슈 제목/번호를 신뢰하지 않고 코드·테스트 실물 대조 (`close_completed_issues.py` 의 번호↔태스크 라벨이 체계적으로 틀렸음 — §부록 A)

## 판정 등급

- **VERIFIED** — GWT 전 시나리오가 코드+테스트로 충족
- **PARTIAL** — 핵심 경로는 있으나 일부 AC 미충족
- **FAKE** — 목/하드코딩/인메모리로 대체되어 규격 미충족
- **ABSENT** — 구현 없음

---

## 1. 감사 결과 요약

| 등급 | 건수 | 이슈 |
|---|---|---|
| VERIFIED | 9 | #12, #18, #21, #28, #38, #42, #44, #45, #46 |
| PARTIAL | 6 | #2, #29(부분 대체), #49, #53, #55, #61 |
| FAKE | 3 | #4, #5, #37 |
| ABSENT | 5 | #3, #7, #8, #9, #10 |
| 정상(추가확인) | 4 | #54, #65, #68, #30 |

**결론: CLOSED 27건 중 8건(#3·#4·#5·#7·#8·#9·#10·#37)은 재오픈이 필요하고, 6건은 잔여 AC를 별도 추적해야 한다.**

---

## 2. ABSENT — 구현 없음 (재오픈 필수)

| 이슈 | 태스크 | 근거 (파일:라인) |
|---|---|---|
| **#3** | ANA-CMD-03 위키 마크다운 생성 및 DB Insert | `INSERT INTO Wiki_Content` **0건**. `Wiki_Content` 참조는 읽기(`analytics_service.py:118` COUNT)와 주석(`rename_service.py:161,239`, `watcher_service.py:224`)뿐. 위키를 **생성하는** 코드 경로가 존재하지 않음 |
| **#7** | ANA-QRY-01 1-Depth 폴더별 위키 마크다운 반환 | 반환 엔드포인트 없음. DTO `WikiMarkdownRes`(`api/dtos.py:82`)는 **정의만 존재하고 사용처 0건** (`grep` 결과 `dtos.py` 외 참조 없음). 반환할 데이터 자체가 #3 미구현으로 없음 |
| **#8** | ANA-QRY-02 분석 진행 상태(Progress) 반환 | 진행률 엔드포인트 없음. DTO `TaskProgressRes`(`api/dtos.py:61`) 역시 **사용처 0건**. DEC-04 비동기 골격 부재와 동일 원인 |
| **#9** | ANA-TEST-01 4포맷 텍스트 추출 정확성 테스트 | `tests/test_ana_cmd_02.py` 는 `.txt`·`.md` 2종만 사용. **`.docx`·`.pdf` 실파일 추출 검증 없음**(`python-docx`/`pdfminer.six` 경로 미검증). 전용 테스트 파일 부재 |
| **#10** | ANA-TEST-02 위키 1-Depth 격리 검증 테스트 | 위키 생성 자체가 없어(#3) 격리 검증 대상이 존재하지 않음. `1depth`/`isolat` 키워드가 걸린 파일들은 청킹·rename·통계 테스트로 위키 격리와 무관 |

---

## 3. FAKE — 목/하드코딩 대체 (재오픈 필수)

| 이슈 | 태스크 | 근거 |
|---|---|---|
| **#4** | ANA-FE-01 고속 분석 정렬 리스트 렌더링 | `grep -rn "fetch(\|axios\|/api/v1" src/frontend/` → **결과 0건**. 프론트엔드 12개 파일(952 LOC) 전체에 API 호출이 하나도 없음. `appStore.ts` 하드코딩 목(`ws-demo-001` + 가짜 파일 3건) 렌더링. `FilesPage` 의 rescan 은 `setTimeout(1500)` |
| **#5** | ANA-FE-02 위키 탭 분리 렌더링 | `WikiPage.tsx` 가 하드코딩 마크다운 문자열을 렌더링. 백엔드 위키 미구현(#3)이므로 결선할 데이터도 없음 |
| **#37** | RN-CMD-01 LLM 템플릿 추천 호출 | 추천값이 `f"2026-08_{name}"` 하드코딩. 실제 LLM 경로는 옵셔널 `mock_llm_callback` 주입 시에만 동작. **단, PII 게이트는 규격대로 실재**(`rename_service.py:8,89` — `PIIFilter.mask` 호출, DEC-17 준수) → 재구현 시 게이트는 보존 |

---

## 4. PARTIAL — 핵심 경로 존재, 잔여 AC 있음

| 이슈 | 태스크 | 충족 | 미충족 (추적 필요) |
|---|---|---|---|
| **#2** | ANA-CMD-02 청킹 및 벡터 DB Insert | 파싱·청킹 실재(`document_parser.py:81`) | **DEC-06 위반**: `vector_service.py:19` 인메모리 `dict`. `chromadb`/`PersistentClient` import **0건**(grep 확인). 임베딩 호출 없음 → 프로세스 종료 시 벡터 전량 소실 |
| **#61** | WS-CMD-01 2개 이상 폴더 병합 | `root_paths` 전체 검증 | `root_paths[0]` 만 저장 → **다중 폴더 병합(PRD 핵심 기능) 미동작**. 스키마 변경(`v002` 마이그레이션) 필요 |
| **#55** | WA-CMD-03 재분석 및 위키 부분 재생성 | 큐 소비·재분석 골격(`watcher_service.py:220~`) | ⓐ 위키 델타 갱신은 docstring 만(`:224`) — `Wiki_Content` write 없음(#3 의존). ⓑ **신규 발견 DEC-11 위반**: `watcher_service.py:248` `file_id = f"file_{int(time.time()*1000)}"` — UUID 아님. 타 모듈은 모두 `str(uuid.uuid4())` 사용(`scanner_service.py:59` 등) → **딥링크·FK 정합성 파괴 위험** |
| **#49** | STAT-CMD-01 통계 이벤트 로깅 | `INSERT INTO Analytics_Log` 실재(`analytics_service.py:52`), `uuid4` 정상, DEC-16 `cost_usd=0.0` 주석 반영 | 실제 LLM 호출이 없어 `tokens_used`/`cost_usd` 가 실측 `usage` 로 채워지는 경로 미검증(#3·LLM 통합 의존) |
| **#53** | WA-CMD-01 Watcher 모드 변경/DB 저장 | 모드 전환·저장 로직 실재 | 워커 스레드 실기동 경로 미연결 (런타임 도달성 미확인) |
| **#29** | LLM-CMD-03 Ollama 프로비저닝 | — | **프로비저닝 코드 0건**: `detect_only`/`assisted`/`onboard`/`api/tags` 전수 grep 결과 실구현 없음(`network_guard.py:25` 화이트리스트 항목과 `query_services.py:170` 의 직접 `urllib` 호출만). `POST /api/v1/llm/onboard`·`Async_Task.result_json.provision_mode` 부재. **`tests/test_llm_cmd_03.py` 는 프로비저닝이 아니라 `LLMResilienceService` 재시도 정책(DEC-16)을 검증** — 파일명과 검증 대상 불일치. 실질 판정은 **ABSENT**, 단 해당 테스트가 검증하는 재시도 로직은 별도로 VERIFIED |

---

## 5. VERIFIED — 규격 충족 (재작업 불필요)

| 이슈 | 태스크 | 근거 |
|---|---|---|
| #12 | API-002 Analysis DTO 정의 | `api/dtos.py` 17개 DTO 정의, 봉투 `ApiResponse`/`ApiError` 포함. *단 `WikiMarkdownRes`·`TaskProgressRes` 는 소비처 없음 — DTO 정의 자체는 AC 충족* |
| #18 | DL-CMD-02 `os.startfile` IPC | `deeplink_service.py:64` `open_file(workspace_id, file_id)` — 호출자 경로 미수용, 서버측 `file_id` 해석 (DEC-08 준수) |
| #21 | DL-QRY-01 Broken Link 검증 | `query_services.py:69,96` 단건/벌크 검증. `current_path` 기준 (DEC-08 준수) |
| #28 | LLM-CMD-02 PII 마스킹 인메모리 적용 | `pii_filter.py` 7종 정규식 + 겹침 병합 후 역순 치환 + 2조건 AND 무결성 검증 + fail-closed (DEC-14 준수) |
| #38 | RN-CMD-02 물리 Rename 및 내역 확정 | `rename_service.py:145` `INSERT INTO Rename_History`, `uuid4` history_id |
| #42 | RN-QRY-01 Diff 매핑 리스트 반환 | `query_services.py:107` `get_pending_rename_diff` |
| #44 | SCAN-CMD-01 트리 순회 및 벌크 Insert | `scanner_service.py:59` `str(uuid.uuid4())` file_id, 블랙리스트 적용 |
| #45 | SCAN-CMD-02 10K Limit Guard | `test_scan_cmd_02.py` 통과 |
| #46 | SCAN-QRY-01 파일수/용량/예상시간 | `query_services.py:35` `get_scan_summary` |
| #65 | WS-QRY-01 워크스페이스 목록/상세 | `query_services.py:15,21` |
| #54 | WA-CMD-02 디바운싱·타임스탬프 대조 | `watcher_service.py` 디바운싱 로직 + `test_wa_cmd_01_02_03.py` |
| #30 | LLM-FE-01 설정 화면 | Option A/B 카드 렌더링 실재. **단 health 상태 표시·API 호출 없음**(`SettingsPage.tsx` 에 `health` 키워드 0건) → 엄밀히는 PARTIAL |

### #68 INF-CMD-03 — PARTIAL로 하향

`NetworkGuard` 자체는 규격 충족(`network_guard.py`: 코드 상수 화이트리스트, exact match, `EgressBlockedError`, `purpose`↔destination 쌍 검증. `test_inf_cmd_03.py:22` 가 `provisioning`→Anthropic 교차 차단까지 검증).

**그러나 AC 의 "import 금지 CI 린트" 가 미구현**: `.github/` 디렉터리 자체가 존재하지 않음(`ls .github/` → No such file or directory). 그 결과 `query_services.py:168` 의 `urllib.request` 직접 import 가 차단되지 않고 통과했다 — **린트가 막아야 했던 위반이 실제로 발생한 것이 곧 린트 부재의 증거**다.

---

## 6. 잘못 열려 있는 이슈 (실제 완료 → close 대상)

`close_completed_issues.py` 의 라벨 오류로 **구현된 태스크의 이슈가 OPEN 상태로 남았다**:

| 이슈 | 태스크 | 실구현 근거 | 조치 |
|---|---|---|---|
| **#11** | API-001 Workspace DTO | `dtos.py:26,41,49` (`WorkspaceCreateReq`/`ItemRes`/`ListRes`) + `test_api_001.py` | **close 가능** |
| **#13** | API-003 LLM/Rename/Watcher/Analytics DTO | `dtos.py:91,103,109,114,119,125,131` + `test_api_002_003.py` | **close 가능** |
| **#15** | DB-001 SQLite 스키마 및 마이그레이션 | `migrations/v001_initial_schema.sql` 8테이블·6인덱스·CASCADE/SET NULL·`strftime('%Y-%m-%dT%H:%M:%fZ','now')` 기본값, `db.py` WAL/`foreign_keys=ON`/`busy_timeout`/thread-local + `test_db.py` | **close 가능** |
| **#39** | RN-CMD-03 Undo 100% 원복 | `rename_service.py:235` `undo_rename`, `Rename_History` 조회(`:245,248`) + `test_rn_cmd_02.py` | **부분** — `ALREADY_UNDONE` 에러코드 미구현(grep 0건, DEC-03 표 항목). 해당 AC 만 잔여 |
| **#27** | LLM-CMD-01 엔진 설정 변경/DB 저장 | `config_manager.py` — **`App_Config` 단일 KV 테이블 기반**(`:48,51,69,109`), DEC-10 준수. API 키는 DPAPI 암호화(`:78,86`), `is_api_key_configured()` 노출(`:100`) + `test_llm_cmd_01.py`·`test_inf_cmd_02.py` | **close 가능** |
| **#23** | INF-CMD-01 MAX_PATH/권한 예외 | `file_utils.py:10` `normalize_path`(`\\?\` 접두), `:29` `safe_file_access` 데코레이터 | **부분** — 글로벌 예외 처리기(DEC-03 `@app.exception_handler`) 미부착. 유틸은 완료 |
| **#17** | DL-CMD-01 Anchor 식별자 DB Update | `deeplink_service.py:10` 앵커 정규식, `:23` `process_wiki_deeplinks` (절대경로 배제 확인) | **부분** — AC 의 "DB Update"(`Wiki_Content.deeplink_mappings` write)가 없음. `deeplink_service.py` 의 유일한 `execute` 는 `:55` **SELECT** 뿐. #3 의존 |
| **#24** | INF-CMD-02 로그 로테이션 + Config 포팅 | Config 포팅(export/import)은 완료(`config_manager.py:123,128` + `test_inf_cmd_02.py`) | **부분** — **로그 로테이션 미구현**: `RotatingFileHandler`/`TimedRotating`/`addHandler`/`basicConfig` 전수 grep **0건**. 즉 **현재 로그가 파일로 전혀 남지 않음** (크래시 진단 수단 부재) |

---

## 7. 권고 조치

### 7.1 재오픈 (8건)
```
#3  ANA-CMD-03  ABSENT  위키 생성 미구현
#7  ANA-QRY-01  ABSENT  위키 반환 엔드포인트 미구현
#8  ANA-QRY-02  ABSENT  진행률 엔드포인트 미구현
#9  ANA-TEST-01 ABSENT  docx/pdf 추출 테스트 없음
#10 ANA-TEST-02 ABSENT  위키 격리 테스트 없음
#4  ANA-FE-01   FAKE    목 데이터 렌더링, API 호출 0건
#5  ANA-FE-02   FAKE    하드코딩 마크다운
#37 RN-CMD-01   FAKE    추천 하드코딩 (PII 게이트는 보존)
#29 LLM-CMD-03  ABSENT  프로비저닝 코드 0건
```
→ 실제 9건 (#29 포함)

### 7.2 close (4건, 규격 충족 확인)
```
#11 API-001, #13 API-003, #15 DB-001, #27 LLM-CMD-01
```

### 7.3 OPEN 유지 + 범위 명확화 (5건)
```
#39 RN-CMD-03  → 잔여: ALREADY_UNDONE 에러코드
#23 INF-CMD-01 → 잔여: 전역 예외 핸들러 부착
#17 DL-CMD-01  → 잔여: deeplink_mappings DB write (#3 의존)
#24 INF-CMD-02 → 잔여: 로그 로테이션 핸들러 부착
#16 DB-002     → ChromaDB 전환 (현 인메모리, #2 와 동일 사안)
```

### 7.4 신규 이슈 필요 (2건)
1. **#68 후속** — DEC-15 import 금지 CI 린트 실제 구성 (`.github/workflows/` 부재)
2. **DEC-11 위반 수정** — `watcher_service.py:248` file_id 를 `str(uuid.uuid4())` 로 교정 (기존 이슈 범위 밖의 신규 결함)

### 7.5 등급 정정 (2건)
```
#68 INF-CMD-03 VERIFIED → PARTIAL (CI 린트 미구성)
#30 LLM-FE-01  CLOSED   → PARTIAL (health 표시/API 호출 없음)
```

---

## 부록 A. `close_completed_issues.py` 라벨 오류 대조표

이 스크립트가 이슈 상태 역전의 직접 원인이다. **삭제 완료** (2026-08-07). 이후 이슈 close 는 `scripts/github_task_tracker.py complete <TASK_ID>` 경로만 사용한다.

| 스크립트 주석 | 실제 #번호 제목 | 일치 |
|---|---|---|
| `2, # ANA-CMD-01` | #2 = ANA-CMD-02 (청킹/벡터) | ❌ |
| `4, # INF-CMD-01` | #4 = ANA-FE-01 | ❌ |
| `5, # INF-CMD-02` | #5 = ANA-FE-02 | ❌ |
| `7, # API-001` | #7 = ANA-QRY-01 | ❌ |
| `8, # API-002` | #8 = ANA-QRY-02 | ❌ |
| `9, # API-003` | #9 = ANA-TEST-01 | ❌ |
| `10, # APP-UI-01` | #10 = ANA-TEST-02 | ❌ |
| `12, # DL-CMD-01` | #12 = API-002 | ❌ |
| `29, # LLM-CMD-02` | #29 = LLM-CMD-03 | ❌ |
| `37, # RN-CMD-01` | #37 = RN-CMD-01 | ✅ |
| `44, 45, 61, 68` | SCAN-CMD-01/02, WS-CMD-01, INF-CMD-03 | ✅ |

**10/14 오류.** 그 결과 구현된 태스크(API-001/003, DB-001, LLM-CMD-01)의 이슈는 OPEN 으로 남고, 미구현 태스크(ANA-QRY-01/02, ANA-TEST-01/02, ANA-FE-01/02, LLM-CMD-03)의 이슈가 "Completed & verified" 코멘트와 함께 CLOSE 되었다.

## 부록 B. 감사에서 새로 발견된 결함 (계획서 예측 밖)

1. **`watcher_service.py:248` DEC-11 위반** — `file_id` 를 타임스탬프 문자열로 생성. 워처가 신규 파일을 등록할 때마다 비-UUID 식별자가 DB 에 삽입되어 딥링크 앵커(`[[file_id:<36자 UUID>]]` 정규식)와 매칭 불가.
2. **로그 파일 핸들러 전무** — `addHandler`/`basicConfig` 0건. 모든 `logger.info/warning` 호출이 어디에도 기록되지 않음. CLAUDE.md 의 "모든 예외는 컨텍스트와 함께 로깅" 요구가 실질적으로 미충족.
3. **`tests/test_llm_cmd_03.py` 명명 오류** — 파일명은 LLM-CMD-03(프로비저닝)이나 내용은 DEC-16 재시도/부분실패/서킷브레이커 검증. 테스트 파일명으로 완료 여부를 판단하면 오판하게 되는 구조.
4. **`WikiMarkdownRes`·`TaskProgressRes` 고아 DTO** — 정의만 있고 소비처 0건. DTO 존재가 기능 존재로 오독될 수 있음.
