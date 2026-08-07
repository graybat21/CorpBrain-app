# CorpBrain MVP 개발 및 GitHub 커밋/푸시 보고서

- **작성 일시**: 2026-08-07
- **원격 저장소**: `https://github.com/graybat21/CorpBrain-app.git`
- **타겟 브랜치**: `docs/grill-dec-01-17`
- **커밋 해시**: `da9210d`
- **커밋 메시지**: `feat: Implement CorpBrain MVP Core Backend & React SPA Frontend (Grill-me T1-T22 resolved, 40 tests pass)`

---

## 1. 주요 푸시 내용 요약

### 1) 백엔드 핵심 도메인 서비스 & 데이터베이스 레이어
- **`DB-001` (메타 DB 엔진)**: `v001_initial_schema.sql` (8개 테이블) 및 WAL 모드, foreign_keys=ON, busy_timeout=5000 기반 스레드 안전 `DatabaseManager` 구축.
- **`INF-CMD-01` (경로 위생 & 예외 처리)**: Windows `MAX_PATH` Prefixing (`\\?\`) 및 OSError/PermissionError 전역 차단 트레이스백 보장.
- **`INF-CMD-02` (보안 키 & 로깅)**: Windows DPAPI 기반 비대칭 암호화(`CryptProtectData`), 로컬 텍스트 일일 로테이션 로그(Max 7일/10MB).
- **`INF-CMD-03` (NetworkGuard Egress 방어막)**: Code-Constant 화이트리스트 기반 3층 무단 외부 유출 차단(`EgressBlockedError`).
- **`LLM-CMD-02` (PII 사전 마스킹 게이트)**: 7종 정규식 패턴 치환 + 2조건 AND `validate_integrity()` Fail-Closed 검증 엔진.
- **`WS-CMD-01` (워크스페이스 관리)**: 다중 폴더 검증, UUID 생성 및 Chroma 컬렉션 선삭제 후 SQLite CASCADE 삭제 (`DEC-09`).
- **`SCAN-CMD-01/02` (파일 스캔 & Limit Guard)**: 재귀적 디렉토리 스캔, 10K 파일 초과 시 `ScanLimitReachedException` 즉시 트리거.
- **`ANA-CMD-01` (구조 기반 고속 분석)**: 파일 트리 뎁스, 확장자, 키워드 사전 가중치 산출 및 `importance_score` DB 갱신.
- **`RN-CMD-01` (파일명 일괄 추천 Diff)**: 절대경로 배제, 상대경로 전송, PII 게이트 재사용 및 Windows 안전 파일명 검증.
- **`DL-CMD-01` (딥링크 Late Binding)**: `[[file_id:UUID]]` 마크다운 파싱 및 클릭 시점 DB 동적 역조회 리졸버.

### 2) REST API & IPC 세션 인증 레이어 (`API-001`, `API-002`, `API-003`)
- FastAPI 앱 기반 `Authorization: Bearer <session_token>` 미들웨어.
- 표준 응답 봉투 `ApiResponse[T]` (`ok: true/false`, `data`, `error`) 정규화.
- 스캔, 고속 분석, LLM 옵션 설정, 파일명 추천 Diff 엔드포인트 수록.

### 3) 프론트엔드 React SPA 레이어 (`APP-UI-01`)
- **React SPA + Vite + Tailwind CSS + Zustand**:
  - `dist/` 정적 번들 빌드 성공 (`dist/index.html`, `dist/assets/*.css`, `dist/assets/*.js`).
  - pywebview 창 타이틀 바 (`TitleBar.tsx`, `-webkit-app-region: drag`).
  - 비차단성 토스트 알림 컴포넌트 (`ToastContainer.tsx`).
  - 5개 핵심 화면 (`DashboardPage.tsx`, `FilesPage.tsx`, `WikiPage.tsx`, `RenamePage.tsx`, `SettingsPage.tsx`).

---

## 2. 검증 현황

- **Pytest 단위/통합 테스트**: **40건 전원 100% Pass** (`python -m pytest tests/`)
- **React SPA 번들 빌드**: **성공** (`npm run build`, 1786 모듈 트랜스폼 완료)
- **통합 구동 스크립트**: **성공** (`python demo_run.py`)
