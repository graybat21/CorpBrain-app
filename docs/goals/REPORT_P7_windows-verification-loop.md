# 루프 P7 실행 보고서 — Windows 검증

- **환경**: Windows 10 Pro (19045), Python 3.10.20 (`.venv`, `requirements.lock.windows.txt`), Node v22.14.0, WebView2 Runtime `pv=151.0.4129.72`
- **기간**: 2026-08-10 ~ 2026-08-11
- **시작 지점**: `main` = `0a52fae` 이후 (`954f56d`)
- **종료 사유**: `QUEUE_EMPTY` (W0~W4 5개 트랙 전부 머지)
- **카운터**: **CORE 1 / MINOR 4** (예산 CORE 3 / MINOR 10 — 미도달)

이 루프의 존재 이유: 직전까지 모든 작업이 macOS 개발 호스트에서 수행돼 **Windows 에서만 증명 가능한 검증이 통째로 미수행**이었다. `WINDOWS_SMOKE_CHECKLIST.md` §5 이력이 비어 있었다. 이 루프는 **명령 출력으로 증명 가능한 범위**를 전부 수행하고, 육안 항목은 사람용 시트로 인계했다.

---

## 1. 트랙별 결과 (전부 머지)

| 트랙 | PR | 요지 | 결과 |
|---|---|---|---|
| **W0** 환경 부트스트랩 | #146 | `.venv`(3.10.20) + `npm ci` + 게이트 5종 | ✅ 게이트 전량 exit 0. 로케일 회귀 1건 수정 |
| **W1** Windows 전용 skip 해소 | #147 | DPAPI·MAX_PATH·handle race 8건 | ✅ 8건 전부 실행·통과. skip-list 플래그 토큰 0건 |
| **W2** exe 빌드·기동 | #148 | onefile 빌드 + `--check-only` | ✅ exit 0. DLL 번들 결함 + TOC 테스트 2건 수정 |
| **W3** 백엔드 실 HTTP 왕복 | #150 | 18기능 실 HTTP + Windows 3조건 | ✅ 18기능 검증. 결함 1건 발견·등재(#149) |
| **W4** 결과 기록·인계 | (이 PR) | 체크리스트 반영 + 매뉴얼 시트 + 보고서 | ✅ |

---

## 2. 자동으로 검증한 항목 (명령 출력으로 증명)

| 항목 | 실행 명령 | 실제 출력 | 판정 |
|---|---|---|---|
| Python 3.10 하한 | `.venv\Scripts\python --version` | `Python 3.10.20` | 통과 |
| 게이트 pytest | `.venv\Scripts\python -m pytest -q` | `737 passed, 6 skipped` | 통과 |
| 게이트 ruff | `.venv\Scripts\ruff check .` | `All checks passed!` | 통과 |
| 게이트 compileall | `.venv\Scripts\python -m compileall -q src scripts tests` | exit 0 | 통과 |
| 게이트 tsc | `npx tsc --noEmit -p tsconfig.json` | exit 0 | 통과 |
| 게이트 vite build | `npx vite build` | `✓ built` exit 0 | 통과 |
| DPAPI 암호화 4건 | `pytest tests/test_inf_cmd_02.py tests/test_llm_cmd_01.py` | 4/4 PASSED | 통과 |
| MAX_PATH 정규화 3건 | `pytest tests/test_inf_cmd_01.py` | 3/3 PASSED | 통과 |
| 파일 핸들 경합 1건 | `pytest tests/test_issue_110.py::...tolerated_on_windows` | PASSED | 통과 |
| skip-list 플래그 토큰 | `pytest -q -rs` SKIPPED 목록 grep | `DPAPI`·`MAX_PATH`·`handle race` **0건** | 통과 |
| exe onefile 단일성 | `Test-Path dist\_internal`, `dir dist` | `_internal`·`CorpBrain\` 부재, `CorpBrain.exe`(52.7MB) 단일 | 통과 |
| exe 헤드리스 기동 | `dist\CorpBrain.exe --check-only` | exit 0 (부팅→마이그레이션→바인딩→health 200→종료) | 통과 |
| 로그 생성·토큰 부재 | `corpbrain.log` + `Select-String "[A-Za-z0-9_-]{40,}"` | `Local API ready on 127.0.0.1:9562` 기록, 토큰류 매치 0건 | 통과 |
| WebView2 탐지(venv) | `python -c "from src.main import detect_webview2_runtime; ..."` | `151.0.4129.72` | 통과 |
| WebView2 탐지(frozen exe) | exe 로그 라인 | `WebView2 Runtime: 151.0.4129.72` | 통과 |
| 루프백 바인딩 | `netstat -ano` (dev_serve) | `TCP 127.0.0.1:8906 ... LISTENING`(`0.0.0.0` 부재) | 통과 |
| 랜덤 포트·비8000 | dev_serve 2회 기동 | RUN1=8906, RUN2=8919 (상이 & ≠8000) | 통과 |
| 무토큰 401 | `GET /api/v1/workspace` (토큰 없이) | `401 UNAUTHORIZED "Missing Bearer token"` | 통과 |
| 스캔 블랙리스트 | W3 실 HTTP `GET /workspace/{id}/file` | `.git`/`node_modules` 제외, 색인 정확히 4건 | 통과 |
| 고속 분석 상위 3개 | W3 `POST /analysis/fast` → `GET /file` | `top_ranked_file_ids` 3건, `importance_score>0` | 통과 |
| **딥링크 os.startfile** | W3 `POST /deeplink/open {file_id}` | `200 {"status":"success"}`, 서버 `os.startfile` 실행(macOS 미실행 경로) | 통과 |
| **실 os.rename 적용** | W3 `POST /rename/apply {items}` | `200 {"status":"applied"}`, 디스크 new 존재·old 소멸 | 통과 |
| **실 os.rename 역방향** | W3 `POST /rename/apply` (new→old) | 원본 복원 | 통과 |
| **MAX_PATH >260 실 스캔** | W3 롱패스(270자) 워크스페이스 스캔 | `201` 생성, 파일 1건 색인 | 통과 |
| **파일 잠금 207** | W3 핸들 보유 중 `POST /rename/apply` | `207 {"status":"multi_status","failed":[{"error_code":"PermissionError"}]}` | 통과 |

---

## 3. 육안·조작이 남은 항목 (미검증 — 사람 몫)

> **에이전트는 WebView2 창을 보지 못한다.** 아래는 전부 미검증이며 `docs/review/WINDOWS_MANUAL_UI_SHEET.md` 로 인계했다. **이 루프는 이 중 어느 것도 "통과" 로 기록하지 않았다.**

| 영역 | 미검증 항목 (요지) | 근거 |
|---|---|---|
| 셸 창 | 창 표시, node.exe 부재, 프로세스 1개, 리사이즈 레이아웃, **흰 화면 깜빡임**(#151) | GUI 육안 |
| WebView2 부재 분기 | 안내 다이얼로그, 자동다운로드 없음, 크래시 없는 종료, per-user 오탐 | 이 PC 에 런타임 설치돼 부재 실증 불가 |
| 프레임리스·드래그 | 커스텀 타이틀바, 드래그 영역, `easy_drag=False`, 텍스트 선택 | GUI 조작 |
| HashRouter | 초기 라우트, 탭 전환, 해시→렌더 구동, 폴백 | TypeScript 런타임(Vitest 미채택) |
| 스캔·대시보드 UI | 프로그레스 바, **Toast**, 캡션 색상 전환(초록↔주황) | GUI 육안 |
| 분석·위키 UI | 정렬 표시, 배지 색, 탭 격리, Broken 배지 | GUI 육안 |
| 이름변경 UI | 행별 승인, 목록 갱신, Undo 반영 | GUI 조작 |
| Watcher UI | 모드 전환, 큐 배지, flush Toast — **#149 수정 후 가능** | 결함 차단 + GUI |
| LLM·Analytics·보안 | 엔진 상태 UI, 단가 기준일, 카드 애니메이션, 패킷 캡처 | 대부분 Ollama·실 LLM 필요(별도 루프) |

---

## 4. 발견·등재한 결함 (미수정 — 다음 루프 인계)

| 이슈 | 분류 | 요지 |
|---|---|---|
| **#149** | **CORE #1 (DEC-05)** | `Watcher_Config.mode` 컬럼이 v001 편집으로 추가돼 기존 DB(user_version=7)에서 watcher 활성화 시 `500 OperationalError`. `mode` 추가 마이그레이션 부재. 권장: `v008_watcher_config_mode.sql` ALTER + 기존-DB 픽스처 회귀 테스트 |
| #145 | (CI 사각지대) | `windows-latest` 잡이 영어/UTF-8 로케일만 검증해 cp949 등 비-UTF-8 로케일 하위프로세스 디코딩 회귀를 못 잡음 |
| #151 | (UI/#14) | `create_window` 에 `background_color` 미지정(기본 `#FFFFFF` vs SPA `bg-slate-950`) — 기동 시 흰 화면 깜빡임 가능. 실제 깜빡임은 육안 확인 필요 |

---

## 5. 루프 내에서 수정한 것 (W0·W1·W2 — 검증 자체를 성립시키기 위한 최소 수정)

| 위치 | 수정 | 트랙 | 뮤테이션/전후 증거 |
|---|---|---|---|
| `tests/test_issue_25.py` | 벤치 하위프로세스 I/O 를 UTF-8 고정(cp949 디코딩 크래시 해소) | W0 | 수정 전 2 failed → 후 9/9 PASS |
| `tests/test_inf_cmd_02.py` | 역분기 skip 사유에서 `DPAPI` 토큰 제거(워딩만) | W1 | skip-list 플래그 토큰 2→0 |
| `CorpBrain.spec` | Anaconda loose DLL 번들 글롭(`Library/bin/*.dll`, 가드) | W2 | 글롭 전 exit 1(pyexpat 크래시) → 후 exit 0 |
| `tests/test_app_ui_01_shell.py` | CArchive TOC 경로 구분자 정규화(`\`→`/`) | W2 | 수정 전 FAILED → 후 PASSED |

---

## 6. 의사결정 카운터 (`CHECKPOINT_P7.md`)

- **CORE 1** — #5 (DEC-05 위반 발견, #149)
- **MINOR 4** — #1(UTF-8 하위프로세스), #2(skip 사유 워딩), #3(DLL 글롭), #4(TOC 구분자)
- 예산(CORE 3 / MINOR 10) 미도달. 종료 사유는 `QUEUE_EMPTY`.

---

## 7. 다음 루프를 위한 인계

1. **#149 를 최우선으로 수정**한다(마이그레이션 `v008`). 이걸 고치기 전엔 Watcher UI(§7) 를 사람도 확인할 수 없다.
2. #151(흰 화면 깜빡임)·#145(CI 로케일)도 함께 처리 후보다.
3. **육안 시트(`WINDOWS_MANUAL_UI_SHEET.md`)를 사람이 1회 수행**하고 판정 기록란을 채운다. 실패 항목은 이슈로 등록한다.
4. §3.8·§3.10 의 LLM/보안 경계 항목은 **Ollama 설치 + 실 LLM 호출 + 패킷 캡처**가 필요하다 — 별도 루프에서 다룬다.
