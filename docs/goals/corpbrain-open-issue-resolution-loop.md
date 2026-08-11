/goal

## 0) 이 문서를 읽는 에이전트에게 — 현재 상태 요약

- **시작 지점**: `main` (직전 루프 P7 종료 시점 = `77b1637`). 열린 PR 0건, 열린 이슈 2건.
- **직전 루프(P7)가 한 일**: Windows 검증(W0~W4) + 그 과정에서 발견한 CORE 결함 #149(Watcher_Config.mode) 수정·머지. 상세는 `docs/goals/REPORT_P7_windows-verification-loop.md`.
- **이 루프가 소진할 대상**: P7 이 등재만 하고 인계한 **열린 이슈 2건** — #151, #145. 신규 기능 개발이 아니라 **인계 결함의 소진**이 이 루프의 존재 이유다.
- **이 루프는 Windows 호스트에서 실행된다.** Python 은 항상 `.venv\Scripts\python` 을 쓴다(메모리의 conda env 가 아니라 P7 이 구성한 `.venv`).

---

## 1) 작업 핵심 목표 및 범위

- **목표**: 현재 열린 GitHub 이슈 **#151·#145 를 이슈별 브랜치 → PR → CI 3잡 pass → squash 머지 사이클로 해소**하여, `gh issue list --state open` 이 이 두 이슈를 더 이상 보이지 않게 만든다.
- **시작 지점**: `main` (= `77b1637` 또는 그 이후). 열린 PR 0건.
- **작업 대상 (이 순서로 처리)**:
  | 순번 | 이슈 | 요지 | 자율 처리 방식 |
  |---|---|---|---|
  | 1 | **#151** | pywebview `create_window` 에 `background_color` 미지정(기본 `#FFFFFF`) vs SPA `bg-slate-950` → 기동 시 흰 화면 깜빡임 가능 | `create_shell_window` 에 `background_color` 지정 + 호출 인자 단위 테스트. **흰 화면 깜빡임의 육안 확인은 에이전트 범위 밖** |
  | 2 | **#145** | CI `windows-latest` 가 비-UTF-8 로케일(cp949) 하위프로세스 디코딩 회귀를 못 잡는 사각지대 | `subprocess` 호출에 `encoding=` 강제를 검증하는 **리포 가드 테스트**(회귀 클래스를 CI-lint 레벨에서 차단). `ci.yml` 로케일 매트릭스는 설계 결정이라 CORE 게이트 적용 |
- **작업 대상에서 제외**:
  - **육안·조작이 필요한 판정** — #151 의 실제 흰 화면 깜빡임 유무. `WINDOWS_MANUAL_UI_SHEET.md` 항목으로 넘기고 **통과로 기록하지 않는다.**
  - **신규 기능 개발**, **Ollama 설치·실 LLM 호출**, **매뉴얼 UI 시트의 육안 항목 수행** — 별도 루프/사람 소관.
- **작업 자율성**: 종료 조건 도달 또는 두 이슈가 모두 머지될 때까지 **사용자 확인 없이 자율 진행**한다. 단 4)의 금지 행동은 예외 없이 적용한다.

---

## 2) 작업 세부 규칙

### 2-1. 이슈당 사이클 (순서 고정)

1. 착수 전 `docs/loop/CHECKPOINT_P8.md` 를 읽는다.
2. `feature/issue-<번호>-<short-kebab>` 브랜치를 `origin/main` 기준으로 생성한다.
3. **먼저 현재 상태를 명령으로 관측한다.** "될 것이다" 로 넘어가지 않는다. 관측 출력을 대화에 남긴 뒤에만 판정한다.
4. 구현한다. 이슈별 특성:
   - **#151**: `src/main.py::create_shell_window` 의 `webview.create_window(...)` 호출에 `background_color="#020617"`(tailwind slate-950) 를 추가한다. 단위 테스트는 `webview.create_window` 를 대체(monkeypatch)해 **전달된 `background_color` 인자값을 단정**한다 — GUI 를 띄우지 않는다. 색상 상수는 SPA 배경과 일치해야 한다.
   - **#145**: `subprocess.run`/`Popen` 등 텍스트 모드 하위프로세스 호출이 `encoding=`(또는 동등한 UTF-8 고정)을 갖추도록 강제하는 **가드 테스트**를 추가한다(예: 리포 소스를 스캔해 위반 0건 단정, 또는 ruff 규칙). P7 에서 고친 `tests/test_issue_25.py` 가 그린으로 남는지도 확인한다.
5. **게이트 5종 전량 실행**: `.venv\Scripts\python -m pytest -q` · `.venv\Scripts\ruff check .` · `.venv\Scripts\python -m compileall -q src scripts tests` · `npx tsc --noEmit -p tsconfig.json` · `npx vite build`. 다섯 모두 exit 0 을 대화에 남긴다.
6. **뮤테이션 검증**: 새로 추가·수정한 핵심 단정마다 대응 구현을 의도적으로 무력화해 **그 테스트가 실제로 실패하는지** 확인하고 즉시 원복한다.
   - **원복에 `git checkout` 을 쓰지 않는다.** 파일 내용을 메모리에 백업했다 되쓰고, 각 치환이 실제로 적용됐는지 assert 한다.
   - **"낱말이 파일에 있는가" 형태의 단정을 쓰지 않는다.** 주석·docstring 을 제거한 본문에서 항목 자체를 본다.
7. 커밋 → push → `gh pr create`. PR 본문에 `Closes #<번호>` 를 넣는다.
8. CI 3잡(`backend macos` / `backend windows` / `frontend`) pass 확인 → `gh pr merge <PR> --squash --delete-branch`.
9. `grep -nE "^(CORE|MINOR):" docs/loop/CHECKPOINT_P8.md` 출력을 대화에 남기고 다음 이슈로 이동한다.

### 2-2. 의사결정 체크포인트 (조기 종료 카운터) — 멀티에이전트 공용 SSOT

- 기록 파일은 **`docs/loop/CHECKPOINT_P8.md`** 하나로 고정한다. 이 루프에 참여하는 **모든 에이전트(메인·서브)는 결정을 기록하기 직전과 종료 판정 직전에 이 파일을 반드시 다시 읽는다.** 다른 어떤 파일·메모리·대화 요약도 카운터의 근거가 되지 않는다.
- 이전 루프의 카운터(`CHECKPOINT_P6.md`·`CHECKPOINT_P7.md`)와 **합산하지 않으며 소급 조정하지 않는다.** `CHECKPOINT_P8.md` 는 0 에서 시작한다.
- 루프 시작 시 이 파일이 없으면 아래 형식으로 **정확히** 생성한다. **`CORE:` / `MINOR:` 두 줄은 grep 대상이므로 형식(콜론·공백·정수)을 바꾸지 않는다.**

```markdown
# CorpBrain Loop Checkpoint — P8 (열린 이슈 소진)

CORE: 0

MINOR: 0

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
```

- **카운트 산정 기준** — `docs/10_CorpBrain_PRD_v1.1_after_grill.md`, `docs/SRS_v1.1_after_grill_OPUS.md`, `.claude/CLAUDE.md` **세 문서 모두에 근거가 없는** 결정만 센다. 하나라도 근거가 있으면 카운트하지 않는다.
  - **CORE (Limit 3)** — 기획 변경, 아키텍처·기술 스택 변경, DEC-01~17 위반 발견, DB 스키마 변경, 신규 외부 의존성 추가, egress 목적지 추가, CI 워크플로 구조 변경, 상위 규격과의 정면 충돌.
  - **MINOR (Limit 10)** — 네이밍, 디렉터리 배치, UI 디테일(색상 상수 등), 로그 포맷, 테스트 픽스처 구조, 상수값 선택.
- 결정이 발생하면 **즉시** 표에 행을 추가하고 같은 편집에서 `CORE:` 또는 `MINOR:` 숫자를 갱신한다. **작업을 계속하기 전에 기록한다.**
- **DEC-01~17 위반을 발견하면 "미구현" 으로 강등하지 말고 즉시 CORE 로 등재한다.**

### 2-3. 도구·명령 규칙 (Windows)

- Python 은 항상 **`.venv\Scripts\python`** 을 사용한다.
- 셸은 PowerShell 기준. 명령이 실패하면 재시도 전에 **실패 출력을 대화에 남긴다.**
- `dev_serve.py` 를 띄운 뒤에는 반드시 종료한다. 테스트가 만든 워크스페이스·파일은 정리하고 `%LocalAppData%\CorpBrain` 의 실 데이터를 오염시키지 않는다.

---

## 3) 종료 조건 및 종료 방법

- **종료 조건** (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/CHECKPOINT_P8.md` 의 `CORE:` 카운터가 **3 에 도달** → STOP REASON: `CORE_BUDGET`
  - `docs/loop/CHECKPOINT_P8.md` 의 `MINOR:` 카운터가 **10 에 도달** → STOP REASON: `MINOR_BUDGET`
  - 대상 이슈(#151·#145)가 **모두 머지 완료** → STOP REASON: `QUEUE_EMPTY`
  - 같은 이슈에서 **CI 실패가 3회 누적**되고 원인이 이 루프 범위 밖으로 판정됨 → STOP REASON: `CI_BLOCKED`
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 **누적 30회 도달** → STOP REASON: `TURN_CAP` (= or stop after 30 turns)

- **종료 방법** (순서대로 실행하고 각 출력을 대화에 남긴다):
  1. `docs/loop/CHECKPOINT_P8.md` 마지막 줄에 `STOP REASON: <코드>` 한 줄을 덧붙인다.
  2. `.venv\Scripts\python -m pytest -q` · `.venv\Scripts\ruff check .` · `.venv\Scripts\python -m compileall -q src scripts tests` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  3. `npx tsc --noEmit -p tsconfig.json` · `npx vite build` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  4. `grep -nE "^(CORE|MINOR|STOP REASON):" docs/loop/CHECKPOINT_P8.md` (PowerShell 이면 `Select-String`) 를 실행해 두 카운터 줄과 STOP REASON 줄이 보이는 출력을 대화에 남긴다.
  5. `gh issue list --state open --limit 100` 을 실행해 남은 열린 이슈 목록을 대화에 남긴다.
  6. `gh pr list --state merged --limit 10` 을 실행해 이 루프가 머지한 PR 목록을 대화에 남긴다.

---

## 4) 기타 제약조건

- **금지 행동**:
  - `main` 에 직접 커밋·푸시 금지. 모든 변경은 브랜치 경유 PR.
  - **`--force` 및 `--force-with-lease` push 금지.** 브랜치를 최신 `main` 위로 올려야 하면 `git merge origin/main` 을 쓴다.
  - **CI 실패를 재실행으로 넘기지 않는다.** 플레이크로 판단되면 원인을 조사해 별도 이슈로 등록하고, pass 확인 후에만 넘어간다.
  - 신규 npm·pip 의존성 추가 금지. `.claude/CLAUDE.md` §4 의 사전 승인 목록 밖이면 추가하지 말고 CORE 로 기록한 뒤 우회 구현한다.
  - DEC-01~17 위반 금지. 위반 발견 시 "미구현" 으로 강등하지 말고 즉시 CORE 로 등재한다.
  - **육안 확인이 필요한 항목을 에이전트가 통과로 기록하지 않는다.** 미검증은 미검증으로 남긴다(#151 의 흰 화면 깜빡임).
  - **실 사용자 데이터 오염 금지**: `%LocalAppData%\CorpBrain\corpbrain_meta.db` 의 기존 워크스페이스를 삭제하지 않는다.

- **수정 금지 파일**:
  - `docs/10_CorpBrain_PRD_v1.0.md`, `docs/10_CorpBrain_PRD_v1.1_after_grill.md`
  - `docs/SRS_v1.1_after_grill_OPUS.md`, `docs/SRS-draft_v0.6_OPUS.md`
  - `.claude/CLAUDE.md`
  - `.github/workflows/ci.yml` — **편집이 불가피하다고 판단되면 먼저 CORE 로 등재**하고 진행 여부를 카운터로 관리한다(무단 편집 금지).
  - `docs/loop/CHECKPOINT.md`, `docs/loop/CHECKPOINT_P6.md`, `docs/loop/CHECKPOINT_P7.md` (종료된 루프의 기록)
  - `docs/goals/REPORT_P6_*.md`, `docs/goals/REPORT_P7_*.md`, 기존 `docs/goals/corpbrain-*-loop.md`
  - 기존 `migrations/v001~v00N_*.sql` (신규 마이그레이션 추가는 허용, 기존 파일 편집은 금지)

- **수정 허용 예외**:
  - `docs/loop/CHECKPOINT_P8.md` — 이 루프의 카운터 파일
  - `docs/review/WINDOWS_MANUAL_UI_SHEET.md` — #151 육안 항목 갱신
  - `docs/goals/REPORT_P8_*.md` — 보고서 신설
  - #151·#145 의 구현·테스트 대상 파일

- **활성 이슈 범위 외 코드 변경 금지.**

---

## 5) 보고 포맷 — 각 PR 본문에 포함

- **관측 대조표**: 검증 항목 → 실행한 명령 → 실제 출력 → 판정(통과/실패/미검증). **"미검증" 을 빈칸으로 두지 않는다.**
- **뮤테이션 검증 출력**: 무력화한 구현 위치 + 그때 실패한 테스트 이름. 무력화해도 통과한 단정이 있었다면 그 사실과 재작성 내용을 함께 적는다.
- **게이트 출력**: pytest / ruff / compileall / tsc / vite build 5개의 exit 상태
- **이 이슈에서 `CHECKPOINT_P8.md` 에 추가한 결정 행** (없으면 "없음" 이라고 명시)
