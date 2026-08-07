# CorpBrain MVP 개발 실행 계획 및 작업 진행 기록 (Task Execution Log)

## 1. 개요
본 문서는 `docs/SRS_v1.1_after_grill_OPUS.md`, `docs/10_CorpBrain_PRD_v1.1_after_grill.md`, `.claude/CLAUDE.md`, `docs/grill/GRILL_LEDGER.md` (DEC-01 ~ DEC-22) 지침에 근거하여 CorpBrain MVP 67개 개발 태스크의 순차적 실행 내역과 검증 결과를 기록하는 문서입니다.

## 2. 모듈 의존성 및 태스크 실행 순서 (Phase)

### Phase 1: 코어 데이터 및 인프라 레이어 (Core Data & Infra Layer)
- [x] **DB-001**: SQLite `corpbrain_meta.db` 스키마 생성 및 마이그레이션 (`DatabaseManager`, `v001_initial_schema.sql`, 스레드-로컬 커넥션, 8개 테이블)
- [x] **INF-CMD-01**: Windows `MAX_PATH` 초과 및 권한 거부 글로벌 예외 처리 (`PermissionError`, `OSError` Interceptor, `normalize_path`)
- [x] **INF-CMD-02**: ConfigManager & Windows DPAPI 암호화 모듈 (`encrypt_secret`, `decrypt_secret`, `config.json` 포팅)
- [x] **INF-CMD-03**: NetworkGuard 단일 egress 관문 구현 (`validate_egress`, `EgressBlockedError`, Egress 3층 방어)
- [x] **LLM-CMD-02**: PII 사전 마스킹 게이트 구현 (7종 정규식, `[PII:TYPE]`, 2조건 AND `validate_integrity`, fail-closed)

### Phase 2: 워크스페이스 & 파일 스캔 레이어 (Workspace & Scanner Layer)
- [x] **WS-CMD-01**: 워크스페이스 CRUD & 선택 관리 (`WorkspaceRepository`, `WorkspaceService`, `DEC-09` 삭제 순서)
- [x] **SCAN-CMD-01**: 파일 스캔 파이프라인 (`ScannerService`, `FileRepository`, 10,000개 리밋, 블랙리스트 제외)
- [x] **SCAN-CMD-02**: 파일 스캔 Limit Guard (`ScanLimitReachedException`, 10K 파일 초과 시 중단)

### Phase 3: 분석 및 LLM 인프라 레이어 (Analysis & LLM Engine)
- [x] **ANA-CMD-01**: 구조 기반 고속 분석 (`FastAnalysisEngine`, `FastAnalysisService`, 가중치 사전 기반 점수 산출 및 DB 업데이트)
- [x] **ANA-CMD-02**: 문서 파싱, 청킹 및 벡터 파이프라인 (`DocumentParser`, `TextChunker`, `VectorDBManager`, `DeepAnalysisService`, `<file_id>:<chunk_index>` 앵커, `delete -> upsert` 순서 고정 `DEC-06` / `DEC-09`)
- [x] **LLM-CMD-01**: Ollama 로컬 임베딩 및 하이브리드 LLM 설정 관리 (`ConfigManager`, `App_Config` SQLite 백엔드, Windows DPAPI 암호화 키 보관 `DEC-10` / `DEC-12` / `DEC-16`)
- [x] **WA-CMD-01**: Watcher 동작 모드 관리 (`WatcherService.update_config`, `Watcher_Config` SQLite 백엔드, Manual/Realtime/Idle/Off 4종 모드 `REQ-FUNC-023`)
- [x] **WA-CMD-02**: `watchdog` 파일 시스템 이벤트 감지, 디바운싱 및 타임스탬프 대조 (`CorpBrainWatcherHandler`, `FileMovedEvent` `file_id` 보존 `DEC-08`, 단순 touch 필터링)
- [x] **WA-CMD-03**: 수정 파일 증분 재분석 및 위키 부분 갱신 (`process_next_queued_item`, `delete_file` -> `upsert` 벡터 파이프라인 `DEC-09`)
- [x] **LLM-CMD-03**: LLM 실패/재시도/부분격리 (`LLMResilienceService`, HTTP 207 Multi-Status 격리, 최대 3회 지수 백오프, 10회 연속 실패 서킷 브레이커 `DEC-16`)
- [x] **RN-CMD-01**: 파일명 추천 Diff 생성 (`RenameService`, 상대경로 전송, PII 게이트 재사용, Windows 파일명 안전성 검증)
- [x] **RN-CMD-02**: 승인된 Diff 기반 OS 레벨 물리 파일 Rename 및 내역 확정 (`apply_rename`, `File_Meta` 커밋 isolation `DEC-05`, `original_path` / `Wiki_Content` 보존 `DEC-08`, 부분 실패 HTTP 207 `DEC-03`)
- [x] **DL-CMD-01**: 딥링크 식별자 매핑 (`DeepLinkService`, `[[file_id:UUID]]` 앵커 파싱, Late Binding 경로 리졸버)

### Phase 4: API & 프론트엔드 UI 레이어 (IPC API & React SPA UI)
- [x] **API-001**: FastAPI IPC 세션 토큰 인증 및 Workspace DTO 명세 (`WorkspaceCreateReq`, `WorkspaceItemRes`, `ApiResponse` 공통 봉투, `Authorization: Bearer` 인증)
- [x] **API-002**: Analysis 도메인 DTO 및 스캔/분석 엔드포인트 (`ScanProgressRes`, `FastAnalysisRes`, `TaskAcceptedRes`, `TaskProgressRes`, `ApiResponse` 봉투)
- [x] **API-003**: LLM Config, Rename, Watcher, Analytics DTO 및 엔드포인트 (`LlmOptionReq`, `LlmHealthCheckRes`, `RenameDiffRes`, `WatcherConfigReq`, `AnalyticsDashboardRes`)
- [x] **APP-UI-01**: React SPA + Tailwind CSS + Shadcn UI + Zustand 스캐폴딩 및 메인 UI 레이아웃 (`dist/` 정적 번들 빌드 성공)

---

## 3. 세부 실행 내역 (Execution History)

### [Phase 1-1] DB-001: SQLite 스키마 및 DatabaseManager 구현
- **목표**: 표준 라이브러리 `sqlite3` 기반의 `PRAGMA user_version` 마이그레이션 러너 및 `DatabaseManager` 구축.
- **주요 반영 사안**:
  - `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`
  - 8개 테이블 스키마 작성 (`v001_initial_schema.sql`)
  - `File_Meta` 경로 컬럼 분리 (`current_path`, `original_path`) 및 `vector_ids` 미포함 (`DEC-09`)
  - UTC ISO-8601 `TEXT` 타임스탬프 규약 적용 (`DEC-11`)
