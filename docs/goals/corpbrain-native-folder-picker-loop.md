/goal

## 0) 이 문서를 읽는 에이전트에게 — 현재 상태 요약

- **시작 지점**: `main` (직전 루프 P9 종료 = `ac34c33` 이상). 열린 PR 0건, 열린 이슈 1건(#163 — chromadb 텔레메트리, 이 루프 범위 밖).
- **요청 배경**: 새 워크스페이스 생성 모달(`src/frontend/components/CreateWorkspaceModal.tsx`)이 폴더 경로를 **텍스트로 직접 입력**받는다. 모달 안 개발 노트가 "OS 네이티브 폴더 선택기는 pywebview 셸 구현 시 추가됩니다 (CON-01 / Issue #14). 현재는 경로를 직접 입력하세요." 라고 명시하듯, 네이티브 폴더 선택기는 **의도적으로 셸 구현 이후로 미뤄둔 계획 기능**이다. 셸(`src/main.py`)은 P6~P9 에서 완성됐으므로 이제 구현 가능하다.
- **핵심 아키텍처 사실**: 브라우저 JS 는 OS 네이티브 "폴더 찾아보기" 다이얼로그를 직접 열 수 없다. pywebview 의 `window.create_file_dialog(webview.FOLDER_DIALOG)` 만이 네이티브 폴더 선택기다. SPA(WebView)가 이를 호출하려면 pywebview `js_api` 브리지(`window.pywebview.api.*`)가 필요하다 — 이것은 **REST(DEC-02/DEC-03) 밖의 새 IPC 채널**이며, 도입 여부·방식은 세 문서에 근거가 있는지 확인해 CHECKPOINT 에 분류·기록해야 하는 결정이다.
- **검증 성격**: 다이얼로그가 실제로 열리고 폴더를 고르는 조작은 **육안·수작업**이다(에이전트는 OS 다이얼로그를 클릭하지 못한다). 명령으로 증명 가능한 부분만 에이전트 범위로 삼고, 나머지는 사람용 시트로 넘긴다.

---

## 1) 작업 핵심 목표 및 범위

- **목표**: 워크스페이스 생성 모달에서 (a) 폴더 경로를 **네이티브 Windows 폴더 선택 다이얼로그**로 고를 수 있게 하고, (b) 사용자가 이름을 직접 입력하지 않았으면 **워크스페이스 이름을 선택한 폴더명으로 기본 채움**한다. 판정: 아래 종료 방법의 게이트·회귀·단위 테스트가 통과하고 exe 가 재빌드·기동(`--check-only` exit 0)한다. (다이얼로그가 실제로 열리는 육안 확인은 제외 — 3) 참조.)
- **시작 지점**: `main` (= `ac34c33` 또는 그 이후). 열린 PR 0건.
- **작업 대상**:
  - `src/frontend/components/CreateWorkspaceModal.tsx` — "폴더 찾기" 버튼, pywebview API 호출, 이름 기본값, 개발 노트 갱신.
  - `src/frontend/api/` 또는 유사 위치 — 폴더 경로에서 워크스페이스 이름을 뽑는 **순수 함수**(예: `deriveWorkspaceName(path)`), 회귀 테스트가 Node 로 실제 실행 가능하도록 `window` 비의존.
  - `src/main.py` — pywebview `js_api` 로 `select_folder()`(→ `create_file_dialog(FOLDER_DIALOG)`) 노출, `create_shell_window` 가 `create_window(..., js_api=...)` 전달.
  - 회귀·단위 테스트 신설.
- **작업 대상에서 제외**:
  - **다이얼로그 실제 열림·폴더 선택·이름 자동 채움의 육안 판정** — `WINDOWS_MANUAL_UI_SHEET.md` 로 넘기고 통과로 기록하지 않는다.
  - **#163(chromadb 텔레메트리)·다른 결함 수정**, **신규 기능 추가** — 별도 루프 소관.
- **작업 자율성**: 종료 조건 도달 또는 구현 머지까지 **사용자 확인 없이 자율 진행**. 단 4)의 금지 행동은 예외 없이 적용한다. **다이얼로그 육안 확인을 위해 루프를 멈추지 않는다.**

---

## 2) 작업 세부 규칙

### 2-1. 사이클 (순서 고정)

1. 착수 전 `docs/loop/CHECKPOINT_P10.md` 를 읽는다.
2. `feature/issue-<번호>-<short-kebab>` 또는 `feat/native-folder-picker` 브랜치를 `origin/main` 기준으로 생성한다.
3. **먼저 현재 상태를 명령으로 관측한다.** pywebview 6.2.1 의 `create_file_dialog`/`js_api` 시그니처를 확인하고 관측 출력을 대화에 남긴 뒤에만 구현한다.
4. 구현한다. 설계 지침:
   - **셸(main.py)**: `js_api` 객체에 `select_folder()` 를 두고 `create_file_dialog(webview.FOLDER_DIALOG)` 결과(선택된 경로 튜플 또는 `None`)를 **단일 경로 문자열 또는 `null`** 로 매핑해 반환. 다이얼로그를 여는 부분과 결과 매핑을 분리해, **GUI 없이 매핑을 단위 테스트**할 수 있게 한다(주입/모의 가능한 seam). `create_shell_window` 가 `create_window(..., js_api=<api>)` 로 넘긴다.
   - **이름 기본값**: 순수 함수 `deriveWorkspaceName(path)` — 경로의 마지막 폴더명(끝 슬래시·빈 입력·드라이브 루트 방어). `window` 를 읽지 않아 Node 로 실제 실행·검증 가능.
   - **모달**: "폴더 찾기" 버튼을 각 경로 입력 옆(또는 상단)에 둔다. `window.pywebview?.api?.select_folder` 가 있으면 호출→경로 필드 채움, 그리고 **이름 필드가 비어 있거나 사용자가 수동 편집하지 않았으면** `deriveWorkspaceName` 으로 이름을 채운다. `window.pywebview` 가 없으면(dev_serve/브라우저) 기존 텍스트 입력과 개발 노트를 **그대로 유지**(우아한 degradation).
5. **게이트 실행**: `npx tsc --noEmit -p tsconfig.json` · `npx vite build` · `.venv\Scripts\python -m pytest -q` · `.venv\Scripts\ruff check .` · `.venv\Scripts\python -m compileall -q src scripts tests`. 전부 exit 0 을 대화에 남긴다.
6. **뮤테이션 검증**: 새로 추가한 핵심 단정마다 대응 구현을 의도적으로 무력화해 그 테스트가 실제로 실패하는지 확인하고 즉시 원복한다.
   - **원복에 `git checkout` 을 쓰지 않는다.** 파일 내용을 메모리에 백업했다 되쓰고, 각 치환이 실제로 적용됐는지 assert 한다.
   - **"낱말이 파일에 있는가" 형태의 단정을 쓰지 않는다.** 순수 함수는 Node 로 실제 실행하고, 셸 매핑은 모의 다이얼로그로 동작을 본다.
7. **실 exe 재빌드·기동**: `npm run build` → `.venv\Scripts\python -m PyInstaller --noconfirm CorpBrain.spec`. `dist\CorpBrain.exe --check-only` **exit 0** 과 기동 후 `GET /` 가 SPA 를 200 서빙함을 대화에 남긴다.
8. 커밋 → push → `gh pr create`. 결함/기능을 이슈로 먼저 등재했다면 PR 본문에 이슈 번호.
9. CI 3잡 pass 확인 → `gh pr merge <PR> --squash --delete-branch`.
10. `grep -nE "^(CORE|MINOR):" docs/loop/CHECKPOINT_P10.md` 출력을 대화에 남긴다.

### 2-2. 의사결정 체크포인트 — 멀티에이전트 공용 SSOT

- 기록 파일은 **`docs/loop/CHECKPOINT_P10.md`** 하나로 고정한다. 모든 에이전트는 결정 기록 직전·종료 판정 직전에 이 파일을 반드시 다시 읽는다.
- 이전 루프 카운터(`CHECKPOINT_P6~P9.md`)와 **합산하지 않으며 소급 조정하지 않는다.** 0 에서 시작한다.
- 루프 시작 시 없으면 아래 형식으로 **정확히** 생성한다. **`CORE:` / `MINOR:` 두 줄은 grep 대상이므로 형식을 바꾸지 않는다.**

```markdown
# CorpBrain Loop Checkpoint — P10 (네이티브 폴더 선택기)

CORE: 0

MINOR: 0

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
```

- **카운트 산정 기준** — `docs/10_CorpBrain_PRD_v1.1_after_grill.md`, `docs/SRS_v1.1_after_grill_OPUS.md`, `.claude/CLAUDE.md` **세 문서 모두에 근거가 없는** 결정만 센다. 하나라도 근거가 있으면 카운트하지 않는다.
  - **CORE (Limit 3)** — 기획 변경, 아키텍처·기술 스택 변경, **REST 밖 신규 IPC 채널 도입(pywebview `js_api`)**, DEC-01~17 위반 발견, DB 스키마 변경, 신규 외부 의존성 추가, egress 목적지 추가, 상위 규격과의 정면 충돌.
  - **MINOR (Limit 10)** — 네이밍, 디렉터리 배치, UI 디테일, 로그 포맷, 테스트 픽스처 구조, 상수값 선택.
- **pywebview `js_api` 브리지 도입은 세 문서에서 근거를 먼저 확인한다.** SRS/Issue #14/CON-01 이 네이티브 다이얼로그를 계획으로 명시하되 그 *기전(js_api)* 까지 규정하지 않는다면, 기전 선택은 CORE 로 등재한다. DEC-02/DEC-03 과 정면 충돌하는지(예: 토큰 없는 데이터 채널이 되는지) 반드시 검토하고, 충돌이면 즉시 CORE.
- 결정 발생 시 **즉시** 표에 행을 추가하고 같은 편집에서 카운터를 갱신한다. 작업을 계속하기 전에 기록한다.

### 2-3. 도구·명령 규칙 (Windows)

- Python 은 항상 **`.venv\Scripts\python`** 을 사용한다.
- 셸은 PowerShell 기준. 명령 실패 시 재시도 전에 실패 출력을 대화에 남긴다.
- **신규 JS 테스트 러너(Vitest/jsdom)를 도입하지 않는다**(스모크 §1). 순수 함수 회귀는 Node(빌드 툴체인)로 확인한다.
- `subprocess` 호출은 텍스트 모드면 `encoding="utf-8"` 을 고정한다(#145 가드가 강제).
- exe/dev_serve 를 띄운 뒤 반드시 종료한다. 테스트로 만든 워크스페이스·파일은 정리하고 `%LocalAppData%\CorpBrain` 의 실 데이터를 오염시키지 않는다(특히 삭제는 #163 로 500 이 날 수 있으니 DB 직접 정리).

---

## 3) 종료 조건 및 종료 방법

- **종료 조건** (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/CHECKPOINT_P10.md` 의 `CORE:` 카운터가 **3 에 도달** → STOP REASON: `CORE_BUDGET`
  - `docs/loop/CHECKPOINT_P10.md` 의 `MINOR:` 카운터가 **10 에 도달** → STOP REASON: `MINOR_BUDGET`
  - 기능 구현 PR 이 **머지 완료** → STOP REASON: `QUEUE_EMPTY`
  - 같은 브랜치에서 **CI 실패가 3회 누적**되고 원인이 이 루프 범위 밖으로 판정됨 → STOP REASON: `CI_BLOCKED`
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 **누적 18회 도달** → STOP REASON: `TURN_CAP` (= or stop after 18 turns)

- **종료 방법** (순서대로 실행하고 각 출력을 대화에 남긴다):
  1. `docs/loop/CHECKPOINT_P10.md` 마지막 줄에 `STOP REASON: <코드>` 한 줄을 덧붙인다.
  2. `npx tsc --noEmit -p tsconfig.json` · `npx vite build` · `.venv\Scripts\python -m pytest -q` · `.venv\Scripts\ruff check .` · `.venv\Scripts\python -m compileall -q src scripts tests` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  3. `deriveWorkspaceName` 순수 함수를 Node 로 실행해 대표 입력(끝 슬래시 포함/미포함, 한글 폴더, 드라이브 루트)에 대한 폴더명 결과를 대화에 남긴다.
  4. `dist\CorpBrain.exe --check-only` 를 실행해 **exit 0** 을 대화에 남긴다.
  5. `grep -nE "^(CORE|MINOR|STOP REASON):" docs/loop/CHECKPOINT_P10.md` 를 실행해 두 카운터 줄과 STOP REASON 줄을 대화에 남긴다.
  6. `gh pr list --state merged --limit 5` 와 `gh issue list --state open --limit 20` 을 실행해 결과를 대화에 남긴다.
  7. **자동 검증한 것 / 육안 확인이 남은 것**(폴더 다이얼로그 실제 열림·폴더 선택·이름 자동 채움·생성)을 분리해 대화에 남긴다. **육안 항목을 통과로 기록하지 않는다.**

---

## 4) 기타 제약조건

- **금지 행동**:
  - `main` 에 직접 커밋·푸시 금지. 모든 변경은 브랜치 경유 PR.
  - **`--force` / `--force-with-lease` push 금지.** 최신 `main` 위로 올릴 땐 `git merge origin/main`.
  - **CI 실패를 재실행으로 넘기지 않는다.** 플레이크면 원인 조사 후 별도 이슈 등록, pass 확인 후 진행.
  - 신규 npm·pip 의존성 추가 금지(특히 JS 테스트 러너). 사전 승인 목록 밖이면 CORE 기록 후 우회.
  - DEC-01~17 위반 금지. 위반 발견 시 즉시 CORE 등재.
  - **js_api 브리지가 토큰·검증 없이 문서/파일 내용·경로를 대량으로 넘기는 데이터 채널이 되지 않게 한다** — 폴더 선택 같은 셸 UI 조작에 한정한다(DEC-02/DEC-03 정신).
  - **육안 확인 항목을 통과로 기록하지 않는다.**
  - **실 사용자 데이터 오염 금지**: `corpbrain_meta.db` 의 기존 워크스페이스 삭제 금지. 테스트로 만든 것만 정리.

- **수정 금지 파일**:
  - `docs/10_CorpBrain_PRD_v1.0.md`, `docs/10_CorpBrain_PRD_v1.1_after_grill.md`
  - `docs/SRS_v1.1_after_grill_OPUS.md`, `docs/SRS-draft_v0.6_OPUS.md`
  - `.claude/CLAUDE.md`, `.github/workflows/ci.yml`
  - `docs/loop/CHECKPOINT.md`, `docs/loop/CHECKPOINT_P6~P9.md` (종료된 루프)
  - `docs/goals/REPORT_P*.md`, 기존 `docs/goals/corpbrain-*-loop.md`
  - 기존 `migrations/v001~v00N_*.sql`

- **수정 허용 예외**:
  - `docs/loop/CHECKPOINT_P10.md`, `docs/review/WINDOWS_MANUAL_UI_SHEET.md`, `docs/goals/REPORT_P10_*.md`
  - 기능 구현·테스트 대상 파일(모달, 순수 함수 모듈, `src/main.py`, 신규 테스트)

- **활성 범위 외 코드 변경 금지.**

---

## 5) 보고 포맷 — PR 본문에 포함

- **관측 대조표**: 검증 항목 → 실행 명령 → 실제 출력 → 판정(통과/실패/미검증). **"미검증" 을 빈칸으로 두지 않는다.**
- **뮤테이션 검증 출력**: 무력화 위치 + 실패한 테스트 이름·메시지.
- **게이트 출력**: tsc / vite build / pytest / ruff / compileall exit 상태 + `deriveWorkspaceName` Node 실행 결과.
- **실 exe 검증**: `--check-only` exit 0, `GET /` 서빙 결과.
- **CHECKPOINT_P10 에 추가한 결정 행**(없으면 "없음"). js_api 도입을 CORE/MINOR/미카운트 중 무엇으로 판정했는지와 그 근거를 반드시 적는다.
- **육안으로 남은 항목**: 폴더 다이얼로그 열림·폴더 선택·이름 자동 채움·생성 (사람이 `dist\CorpBrain.exe` 로 확인).
