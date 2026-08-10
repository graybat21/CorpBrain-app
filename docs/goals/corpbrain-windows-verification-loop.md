/goal

## 0) 이 문서를 읽는 에이전트에게 — 현재 상태 요약

**이 루프는 Windows 호스트에서 실행된다.** 직전까지의 모든 작업은 macOS 개발 호스트에서 수행됐고, 그래서 **Windows 에서만 증명 가능한 검증이 통째로 미수행 상태로 남아 있다.** 이 루프의 존재 이유가 그것이다.

- **시작 지점**: `main` (직전 루프 P6 종료 시점 = `0a52fae`). 열린 이슈 0건, 열린 PR 0건.
- **직전 루프(P6)가 한 일**: `docs/goals/REPORT_P6_open-issues-and-shipping-shell.md` 참조. 요약하면 이슈 #1(고속 분석 상위 3개)·#14(출하 셸) 구현, `src/main.py` + `CorpBrain.spec` 신설, Windows 체크리스트 §3.0 확장, 이슈 대장 정합화.
- **직전 루프가 하지 못한 것**: `CorpBrain.exe` 는 **한 번도 빌드된 적도 실행된 적도 없다.** macOS 산출물은 exe 가 아니며(PyInstaller 는 크로스 컴파일하지 않는다), WebView2·DPAPI·`os.startfile`·MAX_PATH 는 전부 Windows 전용 경로다.
- **`docs/review/WINDOWS_SMOKE_CHECKLIST.md` 의 77개 항목 중 수행된 것은 0건이다.** §5 이력 표가 비어 있다.

**핵심 전제 — 무엇이 에이전트의 몫이고 무엇이 사람의 몫인가.**
체크리스트 77항목 중 상당수는 **육안 확인**(드래그 동작, 레이아웃, 애니메이션, 색상 전환)이다. 에이전트는 GUI 를 보지 못한다. 이 루프는 **명령 출력으로 증명 가능한 검증만** 에이전트의 범위로 삼고, 육안 항목은 사람이 볼 수 있도록 준비·정리해 넘긴다. **육안 항목을 에이전트가 통과로 기록하는 것은 이 루프의 가장 심각한 실패다** — 직전 루프들이 "미검증을 완료로 위장하지 않는다" 를 반복해 지켜온 이유가 이것이다.

---

## 1) 작업 핵심 목표 및 범위

- **목표**: Windows 호스트에서만 증명 가능한 검증을 **명령 출력으로 증명 가능한 범위까지 전부 수행**하고, 그 결과(성공·실패·미수행)를 리포에 기록하여, 이후 누구도 "Windows 에서 확인됐는지" 를 추측하지 않아도 되는 상태로 만든다.

- **시작 지점**: `main` (= `0a52fae` 또는 그 이후). 열린 이슈 0건 · 열린 PR 0건에서 시작한다.

- **작업 대상 — 아래 5개 트랙을 이 순서로 처리한다**:

  | 순번 | 트랙 | 요지 | 에이전트 증명 가능성 |
  |---|---|---|---|
  | 1 | **W0** | **환경 부트스트랩**: `.venv` 구성(`requirements.lock.windows.txt`), `npm ci`, 게이트 5종 통과 확인. `docs/DEVELOPMENT.md` 의 Windows 절차를 따른다. | 전부 명령 출력 |
  | 2 | **W1** | **Windows 전용 테스트 skip 해소**: macOS 에서 skip 되던 DPAPI(4건) · MAX_PATH(3건) · 파일 핸들 경합(1건)이 Windows 에서 **실제로 실행되어 통과**하는지 확인. 실패하면 그것이 이 루프의 첫 실수확이다 — 고친다. | 전부 명령 출력 |
  | 3 | **W2** | **`CorpBrain.exe` 빌드 및 헤드리스 기동 검증**: PyInstaller 로 exe 를 만들고, `--check-only` 로 부팅→마이그레이션→루프백 바인딩→헬스 200→정상 종료를 확인. 단일 파일 여부, 로그 생성, **로그에 세션 토큰 부재**, 레지스트리 WebView2 탐지 실값, `netstat` 바인딩, 무토큰 401 을 명령으로 확인. | 전부 명령 출력 |
  | 4 | **W3** | **백엔드 전 기능 실 HTTP 왕복 (Windows 실 파일시스템)**: `scripts/dev_serve.py` 를 띄우고 워크스페이스 생성 → 스캔 → 고속 분석 → 딥링크 `os.startfile` → Rename/Undo → Watcher → Analytics 를 **실제 HTTP 호출**로 왕복시킨다. macOS 에서는 존재하지 않던 경로(`%LocalAppData%`, `C:\` 절대경로, MAX_PATH 초과, 파일 잠금)를 실제로 통과시키는 것이 목적이다. | 요청·응답 출력 |
  | 5 | **W4** | **결과 기록 및 인계**: 체크리스트에 자동 검증 결과를 반영하고 §5 이력에 수행 행을 남긴다. **육안 확인 항목만 추린 시트**를 신설해 사람이 30분 안에 훑을 수 있게 만든다. 발견된 결함은 `gh issue create` 로 **등재만** 한다. | 파일·이슈 목록 |

- **작업 대상에서 제외**:
  - **육안·조작이 필요한 체크리스트 항목의 판정** — 드래그 영역, 레이아웃, 애니메이션, 색상 전환, Toast 표시 등. W4 에서 사람용 시트로 정리만 하고 **체크하지 않는다.**
  - **발견된 결함의 구현 수정** — W1 에서 드러난 Windows 전용 테스트 실패는 예외적으로 고친다(그 테스트가 통과하는 것이 W1 의 정의이므로). 그 외 결함은 `gh issue create` 로 등재만 하고 이 루프에서 구현하지 않는다.
  - **신규 기능 개발**, **Ollama 설치 및 실 LLM 호출** — 별도 루프 소관.

- **작업 자율성**: 종료 조건에 도달하거나 5개 트랙이 모두 끝날 때까지 **사용자 확인 없이 자율 진행**한다. 단 4)의 금지 행동은 예외 없이 적용한다. **육안 확인을 사용자에게 요청하기 위해 루프를 멈추지 않는다** — W4 의 시트로 넘긴다.

---

## 2) 작업 세부 규칙

### 2-1. 트랙당 사이클 (순서 고정)

1. 트랙 착수 전 `docs/loop/CHECKPOINT_P7.md` 를 읽는다.
2. `feature/windows-<short-kebab>` 브랜치를 `main` 기준으로 생성한다. 문서 전용 트랙(W4)은 `docs/windows-<short-kebab>` 를 쓰고 PR 제목을 `[Docs]` 로 시작한다.
3. **먼저 현재 상태를 명령으로 관측한다.** "될 것이다" 로 넘어가지 않는다. 관측 출력을 대화에 남긴 뒤에만 판정한다.
4. 실패를 발견하면 그것이 이 루프의 수확이다 — W1 범위면 고치고, 아니면 이슈로 등재한다.
5. 게이트 전량 실행: `.venv\Scripts\python -m pytest -q` · `.venv\Scripts\ruff check .` · `.venv\Scripts\python -m compileall -q src scripts tests` · `npx tsc --noEmit -p tsconfig.json` · `npx vite build`.
6. **구현을 고쳤다면 뮤테이션 검증**: 새로 추가·수정한 핵심 단정마다 대응 구현을 의도적으로 무력화해 **그 테스트가 실제로 실패하는지** 확인하고 즉시 원복한다. 실패하지 않는 단정은 다시 쓴다.
   - **원복에 `git checkout` 을 쓰지 않는다.** 작업 트리가 미커밋 상태면 구현 자체가 지워지고, 이후 뮤테이션이 의도한 단정 대신 `AttributeError` 로 "실패" 해 통과처럼 보인다. 파일 내용을 메모리에 백업했다 되쓰고, **각 치환이 실제로 적용됐는지 assert** 한다. (P6 에서 실제로 발생해 1차 결과를 폐기했다)
   - **"낱말이 파일에 있는가" 형태의 단정을 쓰지 않는다.** 그 낱말을 담은 설명 주석이 검사를 통과시킨다. 주석·docstring 을 제거한 본문에서 항목 자체를 보거나, 가능하면 빌드 산출물을 본다. (P6 에서 약한 단정 3건이 이 형태였다)
7. 커밋 → push → `gh pr create`. 발견 결함을 이슈로 등재했다면 PR 본문에 이슈 번호를 적는다.
8. CI 3잡(`backend macos` / `backend windows` / `frontend`) pass 확인 → `gh pr merge <PR> --squash --delete-branch`.
9. `grep -nE "^(CORE|MINOR):" docs/loop/CHECKPOINT_P7.md` 출력을 대화에 남기고 다음 트랙으로 이동한다.

### 2-2. 트랙별 필수 증명 항목

**W0 — 환경 부트스트랩**
- `.venv\Scripts\python --version` 이 **3.10.x** 를 출력한다 (프로젝트 하한, CI 와 동일).
- `requirements.lock.windows.txt` 로 설치한다. **macOS 락 파일을 쓰지 않는다** (pywebview 가 플랫폼별로 다른 백엔드를 끌어온다).
- 게이트 5종이 전부 exit 0.

**W1 — Windows 전용 테스트 skip 해소**
- `.venv\Scripts\python -m pytest -q -rs` 출력의 **SKIPPED 목록에 `DPAPI` · `MAX_PATH` · `handle race` 문자열이 0건**이어야 한다. macOS 에서는 이 8건이 전부 skip 이었다:
  - `tests/test_inf_cmd_02.py` DPAPI 2건, `tests/test_llm_cmd_01.py` DPAPI 2건 (DEC-12 — API 키 암호화)
  - `tests/test_inf_cmd_01.py` MAX_PATH 3건 (CON-04 — 260자 제한, `\\?\` 접두)
  - `tests/test_issue_110.py` 파일 핸들 경합 1건
- skip 이 아닌 **fail** 이 나오면 그것을 고치는 것이 W1 이다. DPAPI 실패는 DEC-12 위반이므로 CORE 후보다.

**W2 — exe 빌드 및 헤드리스 기동**
- 빌드 순서 고정: `npm ci && npm run build` → `.venv\Scripts\python -m PyInstaller --noconfirm CorpBrain.spec`. **역순 금지** — Vite 와 PyInstaller 가 둘 다 `dist\` 를 쓰고 `npm run build` 가 `dist\` 를 비운다.
- `dist\CorpBrain.exe` 가 존재하고, `dist\` 에 `_internal\` 같은 **onedir 산출물 디렉터리가 없다**.
- `dist\CorpBrain.exe --check-only` 가 **exit 0**.
- `%LocalAppData%\CorpBrain\logs\` 에 로그가 생성되고, 그 파일에 **세션 토큰이 없다** (`findstr` 로 확인 — 포트만 남아야 한다).
- `.venv\Scripts\python -c "from src.main import detect_webview2_runtime; print(detect_webview2_runtime())"` 가 **버전 문자열**을 출력한다 (`None` 이면 런타임 부재, `not-windows` 면 플랫폼 판정 버그).
- `dev_serve.py` 기동 중 `netstat -ano` 가 해당 PID 에 대해 **`127.0.0.1:<포트>`** 를 보여준다 (`0.0.0.0` 이면 DEC-02 위반). 두 번 실행 시 **포트가 다르고 8000 이 아니다.**
- 토큰 없이 `/api/v1/workspace` 호출 시 **401**.

**W3 — 백엔드 실 HTTP 왕복**
- `scripts/dev_serve.py` 경유. 요청·응답을 대화에 남긴다.
- **반드시 포함**: 딥링크 열기(`os.startfile` — DEC-08 / REQ-FUNC-021 의 실행 경로. macOS 에서 한 번도 실행된 적 없다), Rename 적용·Undo(실제 파일명 변경), 스캔(블랙리스트·10K 가드), 고속 분석 상위 3개 반환.
- **Windows 고유 조건을 최소 1건씩 실제로 통과시킨다**: 260자 초과 경로, 다른 프로세스가 열어 둔 파일(`PermissionError` 경로), 한글·공백 포함 경로.
- 실패는 은폐하지 않는다. 실패한 호출의 요청·응답을 그대로 남기고 이슈로 등재한다.

**W4 — 결과 기록 및 인계**
- `docs/review/WINDOWS_SMOKE_CHECKLIST.md`: **자동으로 증명한 항목만** 체크하고, 각 체크 옆에 근거 명령을 한 줄로 붙인다. §5 이력 표에 수행 일자·환경·결과 행을 추가한다.
- `docs/review/WINDOWS_MANUAL_UI_SHEET.md` 신설: **육안·조작이 필요한 항목만** 추려 "무엇을 하면 / 무엇이 보여야 하는가" 2열로 정리한다. 자동 검증된 항목은 넣지 않는다.
- 발견 결함은 `gh issue create` 로 등재만 한다. **이 루프에서 구현하지 않는다.**
- 알려진 미등재 가설 1건을 확인하고 처리한다: pywebview `create_window` 의 `background_color` 기본값이 `#FFFFFF` 인데 SPA 는 `bg-slate-950` 이다. 기동 시 흰 화면 깜빡임이 **관측되면** 이슈로 등재한다.

### 2-3. 의사결정 체크포인트 (조기 종료 카운터) — **멀티에이전트 공용 SSOT**

- 기록 파일은 **`docs/loop/CHECKPOINT_P7.md`** 하나로 고정한다. 이 루프에 참여하는 **모든 에이전트(메인·서브 포함)는 결정을 기록하기 직전과 종료 판정 직전에 이 파일을 반드시 다시 읽는다.** 다른 어떤 파일·메모리·대화 요약도 카운터의 근거가 되지 않는다.
- 이전 루프의 카운터(`docs/loop/CHECKPOINT.md`, `docs/loop/CHECKPOINT_P6.md`, `docs/loop/DECISION_LOG.md` 의 `CORE: 6`)와 **합산하지 않으며 소급 조정하지 않는다.** `CHECKPOINT_P7.md` 는 0 에서 시작한다.
- 루프 시작 시 이 파일이 없으면 아래 형식으로 **정확히** 생성한다. **`CORE:` / `MINOR:` 두 줄은 grep 대상이므로 형식(콜론·공백·정수)을 바꾸지 않는다.**

```markdown
# CorpBrain Loop Checkpoint — P7 (Windows 검증)

CORE: 0

MINOR: 0

## 의사결정 기록

| # | 분류 | 트랙 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
```

- **카운트 산정 기준** — `docs/10_CorpBrain_PRD_v1.1_after_grill.md`, `docs/SRS_v1.1_after_grill_OPUS.md`, `.claude/CLAUDE.md` **세 문서 모두에 근거가 없는** 결정만 센다. 세 문서 중 하나라도 근거가 있으면 카운트하지 않는다.
  - **CORE (Limit 3)** — 기획 변경, 아키텍처·기술 스택 변경, DEC-01~17 위반 발견, DB 스키마 변경, 신규 외부 의존성 추가, egress 목적지 추가, 상위 규격과의 정면 충돌.
  - **MINOR (Limit 10)** — 네이밍, 디렉터리 배치, UI 디테일, 로그 포맷, 테스트 픽스처 구조, 상수값 선택.
- 결정이 발생하면 **즉시** 표에 행을 추가하고 같은 편집에서 `CORE:` 또는 `MINOR:` 숫자를 갱신한다. **작업을 계속하기 전에 기록한다** — 몰아서 쓰면 종료 판정 시점의 카운터가 틀린다 (`DECISION_LOG.md` 의 `CORE_BUDGET_EXCEEDED (6/3)` 가 정확히 이 실패였다).
- 서브에이전트를 쓰는 경우, 서브에이전트에게 **이 파일 경로와 갱신 의무를 프롬프트에 그대로 전달**한다. 서브에이전트가 기록하지 못하는 구조라면 그 결정을 메인 에이전트가 대신 기록한 뒤에만 다음 단계로 넘어간다.
- **DEC-01~17 위반을 발견하면 "미구현" 으로 강등하지 말고 즉시 CORE 로 등재한다.**

### 2-4. 도구·명령 규칙 (Windows)

- Python 은 항상 **`.venv\Scripts\python`** 을 사용한다 (macOS 의 `.venv/bin/python` 이 아니다).
- 셸은 PowerShell 을 기준으로 하되, 명령이 실패하면 `cmd` 로 재시도하기 전에 **실패 출력을 대화에 남긴다.**
- 이슈 close 는 `scripts/github_task_tracker.py complete` 경로만 사용한다. 임의 일괄 close 스크립트 금지.
- 임시 파일은 `$env:TEMP` 하위 또는 세션 스크래치패드에 둔다. 리포에 남기지 않는다.
- `dev_serve.py` 를 띄운 뒤에는 **반드시 종료**한다. 다음 트랙이 포트·DB 를 잡고 있는 프로세스와 경합하지 않도록 한다.
- 테스트가 만든 워크스페이스·파일은 정리한다. `%LocalAppData%\CorpBrain` 의 실 데이터를 오염시키지 않는다.

---

## 3) 종료 조건 및 종료 방법

- **종료 조건** (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/CHECKPOINT_P7.md` 의 `CORE:` 카운터가 **3 에 도달** → STOP REASON: `CORE_BUDGET`
  - `docs/loop/CHECKPOINT_P7.md` 의 `MINOR:` 카운터가 **10 에 도달** → STOP REASON: `MINOR_BUDGET`
  - W0~W4 **5개 트랙이 모두 머지 완료** → STOP REASON: `QUEUE_EMPTY`
  - 같은 트랙에서 **CI 실패가 3회 누적**되고 원인이 이 루프 범위 밖으로 판정됨 → STOP REASON: `CI_BLOCKED`
  - **환경 자체가 성립하지 않음** (Python 3.10 미설치, WebView2 Runtime 부재로 W2 진행 불가, 리포 클론 실패 등)이 W0 에서 확정됨 → STOP REASON: `ENV_BLOCKED`
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 **누적 40회 도달** → STOP REASON: `TURN_CAP` (= or stop after 40 turns)

- **종료 방법** (순서대로 실행하고 각 출력을 대화에 남긴다):

  1. `docs/loop/CHECKPOINT_P7.md` 마지막 줄에 `STOP REASON: <코드>` 한 줄을 덧붙인다.
  2. `.venv\Scripts\python -m pytest -q` · `.venv\Scripts\ruff check .` · `.venv\Scripts\python -m compileall -q src scripts tests` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  3. `npx tsc --noEmit -p tsconfig.json` · `npx vite build` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  4. `.venv\Scripts\python -m pytest -q -rs` 를 실행해 **SKIPPED 목록**을 대화에 남기고, 거기에 `DPAPI` · `MAX_PATH` · `handle race` 가 **0건**임을 보인다.
  5. `grep -nE "^(CORE|MINOR|STOP REASON):" docs/loop/CHECKPOINT_P7.md` (PowerShell 이면 `Select-String`) 를 실행해 두 카운터 줄과 STOP REASON 줄이 보이는 출력을 대화에 남긴다.
  6. `dir dist\CorpBrain.exe` 와 `dist\CorpBrain.exe --check-only` 의 **exit 0** 출력을 대화에 남긴다.
  7. `gh issue list --state open --limit 100` 을 실행해 이 루프가 등재한 결함 이슈 목록을 대화에 남긴다.
  8. `gh pr list --state merged --limit 10` 을 실행해 이 루프가 머지한 PR 목록을 대화에 남긴다.
  9. **자동 검증한 항목 / 육안 확인이 남은 항목**을 표 두 개로 분리해 대화에 남긴다. **육안 항목을 검증됨으로 보고하지 않는다.**

---

## 4) 기타 제약조건

- **금지 행동**:
  - `main` 에 직접 커밋·푸시 금지. 모든 변경은 브랜치 경유 PR.
  - **`--force` 및 `--force-with-lease` push 금지.** 브랜치를 최신 `main` 위로 올려야 하면 `git merge origin/main` 을 쓴다 (P6 에서 리베이스 후 force-with-lease 를 써 이 규칙에 저촉됐다).
  - **CI 실패를 재실행으로 넘기지 않는다.** 플레이크로 판단되면 원인을 조사해 별도 이슈로 등록하고, 3회 연속 pass 확인 후에만 넘어간다.
  - 신규 npm·pip 의존성 추가 금지. `.claude/CLAUDE.md` §4 의 사전 승인 목록 밖이면 추가하지 말고 CORE 로 기록한 뒤 우회 구현한다.
  - DEC-01~17 위반 금지. 위반 발견 시 "미구현" 으로 강등하지 말고 즉시 CORE 로 등재한다.
  - **육안 확인이 필요한 항목을 에이전트가 통과로 기록하지 않는다.** 미검증은 미검증으로 남긴다.
  - **실 사용자 데이터 오염 금지**: `%LocalAppData%\CorpBrain\corpbrain_meta.db` 의 기존 워크스페이스를 삭제하지 않는다. 테스트용으로 만든 것만 정리한다.
  - API 키를 실제로 입력해 Option A 로 문서를 전송하지 않는다. DPAPI 검증은 **더미 문자열**로 한다.

- **수정 금지 파일**:
  - `docs/10_CorpBrain_PRD_v1.0.md`, `docs/10_CorpBrain_PRD_v1.1_after_grill.md`
  - `docs/SRS_v1.1_after_grill_OPUS.md`, `docs/SRS-draft_v0.6_OPUS.md`
  - `.claude/CLAUDE.md`, `.github/workflows/ci.yml`
  - `docs/loop/CHECKPOINT.md`, `docs/loop/CHECKPOINT_P6.md` (종료된 루프의 기록)
  - `docs/goals/REPORT_P6_*.md`, `docs/goals/corpbrain-final-open-issues-and-shipping-shell.md`
  - 기존 `migrations/v001~v00N_*.sql` (신규 마이그레이션 추가는 허용, 기존 파일 편집은 금지)

- **수정 허용 예외** (이번 루프에서 명시적으로 허용):
  - `docs/loop/CHECKPOINT_P7.md` — 이 루프의 카운터 파일
  - `docs/review/WINDOWS_SMOKE_CHECKLIST.md` — 자동 검증 결과 반영 및 §5 이력 기록
  - `docs/review/WINDOWS_MANUAL_UI_SHEET.md` — 신설
  - `docs/DEVELOPMENT.md` — Windows 절차에 실제로 빠진 것이 있었다면 보강
  - `docs/goals/` — 보고서 추가
  - W1 에서 실패한 Windows 전용 경로의 구현·테스트

- **활성 트랙 범위 외 코드 변경 금지.**

---

## 5) 의존성 및 사전 조건

W0 에서 아래를 **명령으로 확인**하고, 충족되지 않으면 그 사실을 대화에 남긴 뒤 `ENV_BLOCKED` 판정 여부를 정한다.

| 항목 | 확인 명령 | 불충족 시 |
|---|---|---|
| 리포 최신화 | `git log --oneline -1` 이 `0a52fae` 이상 | `git pull` |
| Python 3.10 | `python --version` | 3.10 설치 필요 → `ENV_BLOCKED` |
| Node | `node --version` (CI 는 22) | 설치 필요 |
| gh CLI 인증 | `gh auth status` | `gh auth login` 은 사용자 몫 → 대화에 요청만 남기고 다른 트랙 진행 |
| WebView2 Runtime | `.venv\Scripts\python -c "from src.main import detect_webview2_runtime; print(detect_webview2_runtime())"` | `None` 이면 **그 자체가 W2 의 유효한 관측 결과다** — 안내 다이얼로그 분기를 실제로 확인할 기회이므로 `ENV_BLOCKED` 가 아니다 |
| Ollama | 미설치가 기본 전제 | 설치하지 않는다. 관련 테스트 skip 유지 |

---

## 6) 보고 포맷 — 각 PR 본문에 포함

- **관측 대조표**: 검증 항목 → 실행한 명령 → 실제 출력 → 판정(통과/실패/미검증). **"미검증" 을 빈칸으로 두지 않는다.**
- **뮤테이션 검증 출력** (구현을 고친 트랙만): 무력화한 구현 위치 + 그때 실패한 테스트 이름. 무력화해도 통과한 단정이 있었다면 **그 사실과 재작성 내용을 함께 적는다.**
- **게이트 출력**: pytest / ruff / compileall / tsc / vite build 5개의 exit 상태
- **실 HTTP 호출** (W2·W3): 요청·응답 원문
- **등재한 이슈 번호**와 등재하지 않기로 한 관측이 있다면 그 사유
- **이 트랙에서 `CHECKPOINT_P7.md` 에 추가한 결정 행** (없으면 "없음" 이라고 명시)
