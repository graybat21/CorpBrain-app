/goal

## 0) 이 문서를 읽는 에이전트에게 — 현재 상태 요약

- **시작 지점**: `main` (직전 루프 P8 종료 + 출하 exe 셸 크래시 수정 #159 반영 시점 = `530f4f7` 이상). 열린 PR 0건, 열린 이슈 0건.
- **버그 현상**: 데스크톱 셸(또는 브라우저)에서 워크스페이스를 생성하면 Toast `워크스페이스 생성 실패: Failed to construct 'URL': Invalid base URL` 이 뜨고 생성되지 않는다. 이는 워크스페이스 생성만이 아니라 **SPA 의 모든 API 호출**에 영향을 준다.
- **근본 원인 (확정)**: `src/frontend/api/client.ts` 의 `buildUrl` 이 `new URL(path, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`)` 를 호출한다. 셸(`src/main.py`)과 `scripts/dev_serve.py` 가 브리지에 주입하는 `baseUrl` 은 **`"/"`** (포트를 마크업에 박지 않으려는 의도) 인데, WHATWG `URL` 생성자는 **base 가 절대 URL 이 아니면 `TypeError: Invalid base URL`** 을 던진다. `"/"` 는 상대 URL 이라 실패한다.
- **왜 지금까지 검증이 놓쳤나**: 직전 루프들의 실 HTTP 검증은 `http://127.0.0.1:<port>/api/v1/...` **전체 URL 로 백엔드를 직접 호출**해 이 프론트엔드 URL 조립 경로를 우회했다. 백엔드는 정상이고, 결함은 순수 클라이언트 측 JS 다.

---

## 1) 작업 핵심 목표 및 범위

- **목표**: `src/frontend/api/client.ts` 의 URL 조립을 고쳐, `baseUrl="/"` 일 때도 `buildUrl` 이 **던지지 않고 유효한 절대 URL** 을 만들어 SPA 의 API 호출(워크스페이스 생성 포함)이 성립하게 한다. 판정: 아래 종료 방법의 회귀 검증 명령이 통과하고 게이트 3종이 exit 0.
- **시작 지점**: `main` (= `530f4f7` 또는 그 이후). 열린 PR 0건.
- **작업 대상**: `src/frontend/api/client.ts` (버그 지점). 필요 시 이 결함을 고정하는 회귀 테스트 파일 신설. `src/main.py` / `scripts/dev_serve.py` 의 `baseUrl` 주입값 자체는 **바꾸지 않는 것을 기본**으로 한다 — 포트를 마크업에 박지 않는 현 설계(주석에 근거 명시됨)를 유지하고, 클라이언트에서 `window.location` 에 대해 상대 base 를 절대화하는 방향이 우선이다. (셸/서버 쪽 변경이 불가피하다고 판단되면 그 사유를 CHECKPOINT_P9 에 기록한다.)
- **작업 자율성**: 종료 조건 도달 또는 버그 수정 머지까지 **사용자 확인 없이 자율 진행**한다. 단 4)의 금지 행동은 예외 없이 적용한다. **창 안에서 실제로 워크스페이스가 생성되는지의 육안 확인을 위해 루프를 멈추지 않는다** — 사람용 시트로 넘긴다.

---

## 2) 작업 세부 규칙

### 2-1. 사이클 (순서 고정)

1. 착수 전 `docs/loop/CHECKPOINT_P9.md` 를 읽는다.
2. `feature/issue-<번호>-<short-kebab>` (이슈를 먼저 등재한 경우) 또는 `fix/workspace-url-base` 브랜치를 `origin/main` 기준으로 생성한다.
3. **먼저 현재 상태를 명령으로 관측한다.** 특히 `node` 로 **수정 전 표현식이 실제로 던지는지** 재현해 대화에 남긴 뒤에만 수정한다("될 것이다" 금지).
4. 수정한다. `new URL(path, base)` 의 `base` 를 `window.location.href`(또는 `window.location.origin`)에 대해 먼저 절대화한다. 절대 `baseUrl`(개발 시 전체 URL) 도 그대로 동작해야 한다.
5. **회귀 테스트를 추가한다.** WHATWG `URL` 은 Node 와 브라우저에서 동일하므로 `node` 로 실행 가능한 검증을 붙인다 — `baseUrl="/"` + 고정 origin 에서 조립 결과가 `http://.../api/v1/workspace` 형태의 **유효한 절대 URL** 임을 단정하고, **수정 전 형태(`new URL('api/v1/workspace', '/')`)는 던짐**을 함께 단정한다. 소스 문자열 grep 이 아니라 **실제 URL 조립 로직의 동작**을 본다.
6. **게이트 실행**: `npx tsc --noEmit -p tsconfig.json` · `npx vite build` · `.venv\Scripts\python -m pytest -q` (+ 회귀 검증 명령). 전부 exit 0 을 대화에 남긴다.
7. **뮤테이션 검증**: 수정을 의도적으로 무력화(base 절대화 제거)해 5)의 회귀 테스트가 **실제로 실패**하고 그 실패 메시지가 프로덕션 에러(`Invalid base URL`)와 같은지 확인한 뒤 즉시 원복한다.
   - **원복에 `git checkout` 을 쓰지 않는다.** 파일 내용을 메모리에 백업했다 되쓰고, 각 치환이 실제로 적용됐는지 assert 한다.
8. **실 exe 재빌드·기동**: `npm run build` → `.venv\Scripts\python -m PyInstaller --noconfirm CorpBrain.spec` (순서 고정). `dist\CorpBrain.exe --check-only` **exit 0** 과, 기동 후 `GET /` 가 SPA(세션 브리지 주입 포함)를 200 으로 서빙함을 대화에 남긴다.
9. 커밋 → push → `gh pr create`. 결함을 이슈로 먼저 등재했다면 PR 본문에 `Closes #<번호>`.
10. CI 3잡(`backend macos` / `backend windows` / `frontend`) pass 확인 → `gh pr merge <PR> --squash --delete-branch`.
11. `grep -nE "^(CORE|MINOR):" docs/loop/CHECKPOINT_P9.md` 출력을 대화에 남긴다.

### 2-2. 의사결정 체크포인트 (조기 종료 카운터) — 멀티에이전트 공용 SSOT

- 기록 파일은 **`docs/loop/CHECKPOINT_P9.md`** 하나로 고정한다. 이 루프의 **모든 에이전트(메인·서브)는 결정을 기록하기 직전과 종료 판정 직전에 이 파일을 반드시 다시 읽는다.** 다른 어떤 파일·메모리·대화 요약도 카운터의 근거가 되지 않는다.
- 이전 루프 카운터(`CHECKPOINT_P6/P7/P8.md`)와 **합산하지 않으며 소급 조정하지 않는다.** `CHECKPOINT_P9.md` 는 0 에서 시작한다.
- 루프 시작 시 이 파일이 없으면 아래 형식으로 **정확히** 생성한다. **`CORE:` / `MINOR:` 두 줄은 grep 대상이므로 형식(콜론·공백·정수)을 바꾸지 않는다.**

```markdown
# CorpBrain Loop Checkpoint — P9 (워크스페이스 URL 버그 수정)

CORE: 0

MINOR: 0

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
```

- **카운트 산정 기준** — `docs/10_CorpBrain_PRD_v1.1_after_grill.md`, `docs/SRS_v1.1_after_grill_OPUS.md`, `.claude/CLAUDE.md` **세 문서 모두에 근거가 없는** 결정만 센다. 하나라도 근거가 있으면 카운트하지 않는다.
  - **CORE (Limit 3)** — 기획 변경, 아키텍처·기술 스택 변경, DEC-01~17 위반 발견, DB 스키마 변경, 신규 외부 의존성 추가(예: JS 테스트 러너 도입), egress 목적지 추가, 상위 규격과의 정면 충돌.
  - **MINOR (Limit 10)** — 네이밍, 디렉터리 배치, UI 디테일, 로그 포맷, 테스트 픽스처 구조, 상수값 선택, 회귀 테스트 실행 수단 선택.
- 결정이 발생하면 **즉시** 표에 행을 추가하고 같은 편집에서 `CORE:` 또는 `MINOR:` 숫자를 갱신한다. **작업을 계속하기 전에 기록한다.**
- **DEC-01~17 위반을 발견하면 "미구현" 으로 강등하지 말고 즉시 CORE 로 등재한다.**

### 2-3. 도구·명령 규칙 (Windows)

- Python 은 항상 **`.venv\Scripts\python`** 을 사용한다 (PATH 의 `python` 은 깨진 Store 스텁).
- 셸은 PowerShell 기준. 명령이 실패하면 재시도 전에 **실패 출력을 대화에 남긴다.**
- **신규 JS 테스트 러너(Vitest/jsdom 등)를 도입하지 않는다** — 스모크 체크리스트 §1 의 확정 결정과 충돌한다. 회귀 검증은 이미 있는 `node`(빌드 툴체인) 로 WHATWG URL 동작을 확인하는 방식을 쓴다. 도입이 불가피하다고 판단되면 CORE 로 기록하고 우회한다.
- `dev_serve.py`/exe 를 띄운 뒤에는 반드시 종료한다. 테스트가 만든 워크스페이스·파일은 정리하고 `%LocalAppData%\CorpBrain` 의 실 데이터를 오염시키지 않는다.

---

## 3) 종료 조건 및 종료 방법

- **종료 조건** (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/CHECKPOINT_P9.md` 의 `CORE:` 카운터가 **3 에 도달** → STOP REASON: `CORE_BUDGET`
  - `docs/loop/CHECKPOINT_P9.md` 의 `MINOR:` 카운터가 **10 에 도달** → STOP REASON: `MINOR_BUDGET`
  - 버그 수정 PR 이 **머지 완료** → STOP REASON: `QUEUE_EMPTY`
  - 같은 브랜치에서 **CI 실패가 3회 누적**되고 원인이 이 루프 범위 밖으로 판정됨 → STOP REASON: `CI_BLOCKED`
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 **누적 15회 도달** → STOP REASON: `TURN_CAP` (= or stop after 15 turns)

- **종료 방법** (순서대로 실행하고 각 출력을 대화에 남긴다):
  1. `docs/loop/CHECKPOINT_P9.md` 마지막 줄에 `STOP REASON: <코드>` 한 줄을 덧붙인다.
  2. `npx tsc --noEmit -p tsconfig.json` · `npx vite build` · `.venv\Scripts\python -m pytest -q` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  3. 회귀 검증 명령(`node` 기반)을 실행해 `baseUrl="/"` 조립이 **유효한 절대 URL 을 만들고 수정 전 형태는 던진다** 는 출력을 대화에 남긴다.
  4. `dist\CorpBrain.exe --check-only` 를 실행해 **exit 0** 을 대화에 남긴다.
  5. `grep -nE "^(CORE|MINOR|STOP REASON):" docs/loop/CHECKPOINT_P9.md` (PowerShell 이면 `Select-String`) 를 실행해 두 카운터 줄과 STOP REASON 줄이 보이는 출력을 대화에 남긴다.
  6. `gh pr list --state merged --limit 5` 와 `gh issue list --state open --limit 20` 을 실행해 결과를 대화에 남긴다.
  7. **자동 검증한 것 / 육안 확인이 남은 것**(창 안에서 실제 워크스페이스가 생성되는가)을 분리해 대화에 남긴다. **육안 항목을 통과로 기록하지 않는다.**

---

## 4) 기타 제약조건

- **금지 행동**:
  - `main` 에 직접 커밋·푸시 금지. 모든 변경은 브랜치 경유 PR.
  - **`--force` 및 `--force-with-lease` push 금지.** 브랜치를 최신 `main` 위로 올려야 하면 `git merge origin/main` 을 쓴다.
  - **CI 실패를 재실행으로 넘기지 않는다.** 플레이크로 판단되면 원인을 조사해 별도 이슈로 등록하고, pass 확인 후에만 넘어간다.
  - 신규 npm·pip 의존성 추가 금지(특히 JS 테스트 러너). 사전 승인 목록 밖이면 CORE 로 기록한 뒤 우회 구현한다.
  - DEC-01~17 위반 금지. 위반 발견 시 즉시 CORE 로 등재한다.
  - **육안 확인이 필요한 항목을 에이전트가 통과로 기록하지 않는다.** 창 안 실제 생성은 미검증으로 남긴다.
  - **실 사용자 데이터 오염 금지**: `%LocalAppData%\CorpBrain\corpbrain_meta.db` 의 기존 워크스페이스를 삭제하지 않는다. 테스트로 만든 것만 정리한다.

- **수정 금지 파일**:
  - `docs/10_CorpBrain_PRD_v1.0.md`, `docs/10_CorpBrain_PRD_v1.1_after_grill.md`
  - `docs/SRS_v1.1_after_grill_OPUS.md`, `docs/SRS-draft_v0.6_OPUS.md`
  - `.claude/CLAUDE.md`, `.github/workflows/ci.yml`
  - `docs/loop/CHECKPOINT.md`, `docs/loop/CHECKPOINT_P6.md`, `docs/loop/CHECKPOINT_P7.md`, `docs/loop/CHECKPOINT_P8.md` (종료된 루프)
  - `docs/goals/REPORT_P*.md`, 기존 `docs/goals/corpbrain-*-loop.md`
  - 기존 `migrations/v001~v00N_*.sql`

- **수정 허용 예외**:
  - `docs/loop/CHECKPOINT_P9.md` — 이 루프의 카운터 파일
  - `docs/review/WINDOWS_MANUAL_UI_SHEET.md` — 창 안 생성 육안 항목 반영
  - `docs/goals/REPORT_P9_*.md` — 보고서 신설
  - 버그 수정·회귀 테스트 대상 파일

- **활성 범위 외 코드 변경 금지.**

---

## 5) 보고 포맷 — PR 본문에 포함

- **관측 대조표**: 검증 항목 → 실행한 명령 → 실제 출력 → 판정(통과/실패/미검증). **"미검증" 을 빈칸으로 두지 않는다.**
- **뮤테이션 검증 출력**: 무력화한 구현 위치 + 그때 실패한 테스트 이름·메시지. 무력화해도 통과한 단정이 있었다면 그 사실과 재작성 내용을 함께 적는다.
- **게이트 출력**: tsc / vite build / pytest exit 상태 + 회귀 검증(node) 출력
- **실 exe 검증**: `--check-only` exit 0, `GET /` 서빙 결과
- **CHECKPOINT_P9 에 추가한 결정 행** (없으면 "없음" 이라고 명시)
- **육안으로 남은 항목**: 창 안에서 워크스페이스가 실제로 생성되는지 (사람이 `dist\CorpBrain.exe` 로 확인)
