/goal

## 1) 작업 핵심 목표 및 범위

- **목표**: 현재 열려 있는 CorpBrain GitHub 이슈 중 **테스트 부채 8건과 UI 잔여 3건(총 11건)** 을 이슈당 1개의 PR 로 구현하고, 각 PR 의 CI 3잡(`backend macos` / `backend windows` / `frontend`)이 pass 한 상태로 만든다.

- **시작 지점**: `main` (현재 HEAD). 열린 PR 은 0건이다.

- **작업 대상 — 아래 11건을 이 순서로 처리한다** (선행 의존이 이미 해소된 것부터, 같은 모듈끼리 인접 배치):

  | 순번 | 이슈 | 태스크 ID | 비고 |
  |---|---|---|---|
  | 1 | #47 | SCAN-TEST-01 | 스캔 블랙리스트 단위 테스트 |
  | 2 | #48 | SCAN-TEST-02 | 10K Limit Guard 단위 테스트 (#47 과 동일 모듈) |
  | 3 | #9  | ANA-TEST-01 | 4개 포맷 텍스트 추출 정확성 |
  | 4 | #10 | ANA-TEST-02 | 위키 1-Depth 격리 침범 검증 |
  | 5 | #22 | DL-TEST-01 | Broken Link 실시간 검증 |
  | 6 | #43 | RN-TEST-01 | Undo 100% 원복 통합 테스트 |
  | 7 | #34 | LLM-TEST-02 | Health Check·재시도·부분 실패 정책 |
  | 8 | #66 | WS-TEST-01 | 폴더 병합 + 앱 재시작 영속성 |
  | 9 | #51 | STAT-QRY-01 | WPM 통계 산출 (구현 존재, AC 대조 필요) |
  | 10 | #52 | STAT-TEST-01 | WPM 절약 시간 단위 테스트 (#51 선행) |
  | 11 | #50 | STAT-FE-01 | My Analytics 차트 UI (#51 선행) |

- **작업 대상에서 제외 — 착수하지 않는다**:
  - **#14 (APP-UI-01 pywebview 셸 + PyInstaller `.spec`)** — 출하 산출물 검증에 **Windows 호스트가 필수**이며 현재 개발 호스트는 macOS 다. macOS 에서 "완료" 를 증명할 수단이 없으므로 이 루프의 범위 밖이다.
  - **#25 (INF-TEST-01 p95 성능 부하 테스트)** — 성능 수치는 러너 부하에 좌우되어 CI 에서 boolean 판정이 불안정하다. 별도 판단이 필요하다.
  - **#6 / #64 / #68 / #35 / #36 / #94 / #17 / #30** — 아래 5) 참조. 규격 충돌·중복·목적 소멸 판단이 필요한 항목이므로 **코드를 건드리지 않고 판단만 기록**한다.

- **작업 자율성**: 종료 조건에 도달하거나 11건이 모두 끝날 때까지 **사용자 확인 없이 자율 진행**한다. 단 아래 4) 의 금지 행동은 예외 없이 적용한다.

---

## 2) 작업 세부 규칙

### 2-1. 이슈당 사이클 (순서 고정)

1. `gh issue view <N>` 으로 AC(GWT)를 **한 항목씩** 읽는다. 이슈 제목·라벨·기존 판정을 신뢰하지 않는다.
2. `python scripts/github_task_tracker.py start <TASK_ID>` 실행.
3. `feature/issue-<N>-<short-kebab>` 브랜치 생성 (`main` 기준).
4. **먼저 현재 구현이 AC 를 만족하는지 코드로 대조**한다. 미충족 항목이 있으면 구현을 고친다.
5. 테스트 작성 → 실행 → 통과.
6. **뮤테이션 검증**: 새로 추가한 핵심 단정마다, 대응하는 구현을 의도적으로 되돌리거나 무력화해 **그 테스트가 실제로 실패하는지** 확인하고 즉시 원복한다. 실패하지 않는 단정은 무의미하므로 다시 쓴다. 이 확인 출력을 PR 본문에 남긴다.
7. 게이트 전량 실행: `.venv/bin/python -m pytest -q` · `.venv/bin/ruff check .` · `.venv/bin/python -m compileall -q src scripts tests` · `npx tsc --noEmit -p tsconfig.json` · `npx vite build`.
8. 엔드포인트를 추가·수정했다면 `scripts/dev_serve.py` 로 **실제 HTTP 호출 1회**를 수행하고 그 출력을 PR 본문에 넣는다 (DECISION_LOG 재발 방지 5).
9. 커밋 → push → `gh pr create` (본문에 `Closes #<N>` 필수).
10. CI 3잡 pass 확인 → `gh pr merge <PR> --squash --delete-branch`.
11. `python scripts/github_task_tracker.py complete <TASK_ID>` 실행 후 `gh issue edit <N> --remove-label in-progress`.
12. 다음 이슈로 이동.

### 2-2. 의사결정 체크포인트 (조기 종료 카운터)

- 기록 파일은 **`docs/loop/CHECKPOINT.md`** 하나로 고정한다. 멀티에이전트가 **이 파일만 읽어** 현재 카운트를 알 수 있어야 한다.
- 루프 시작 시 이 파일이 없으면 아래 형식으로 생성한다. **`CORE:` / `MINOR:` 두 줄은 grep 대상이므로 형식을 바꾸지 않는다.**

```markdown
# CorpBrain Loop Checkpoint

CORE: 0
MINOR: 0

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 근거 문서 부재 사유 |
|---|---|---|---|---|
```

- **카운트 산정 기준** — `docs/10_CorpBrain_PRD_v1.1_after_grill.md`, `docs/SRS_v1.1_after_grill_OPUS.md`, `.claude/CLAUDE.md` **세 문서 모두에 근거가 없는** 결정만 센다. 세 문서 중 하나라도 근거가 있으면 카운트하지 않는다.

  - **CORE (Limit 3)** — 기획 변경, 아키텍처·기술 스택 변경, DEC-01~17 위반 발견, 스키마 변경, 신규 외부 의존성 추가, egress 목적지 추가, AC 와 상위 규격의 정면 충돌.
  - **MINOR (Limit 10)** — 네이밍, 디렉터리 배치, UI 디테일, 로그 포맷, 테스트 픽스처 구조, 상수값 선택.

- 결정이 발생하면 **즉시** 해당 행을 표에 추가하고 `CORE:` 또는 `MINOR:` 숫자를 갱신한다. **작업을 계속하기 전에 기록한다** — 나중에 몰아서 쓰면 카운터가 종료 판정 시점에 틀린다.
- 이미 종료된 과거 루프의 `docs/loop/DECISION_LOG.md` 카운터(`CORE: 6`)는 **소급 조정하지 않으며 이 루프의 카운트와 합산하지 않는다.** `CHECKPOINT.md` 는 0 에서 시작한다.

### 2-3. 도구·명령 규칙

- Python 은 `.venv/bin/python` 을 사용한다 (시스템 python 은 3.12 이며 프로젝트는 3.10 이다).
- 이슈 close 는 `scripts/github_task_tracker.py complete` 경로만 사용한다. 임의 일괄 close 스크립트 금지.
- 임시 파일은 `$CLAUDE_JOB_DIR/tmp` 에 둔다.

---

## 3) 종료 조건 및 종료 방법

- **종료 조건** (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/CHECKPOINT.md` 의 `CORE:` 카운터가 **3 에 도달** → STOP REASON: `CORE_BUDGET`
  - `docs/loop/CHECKPOINT.md` 의 `MINOR:` 카운터가 **10 에 도달** → STOP REASON: `MINOR_BUDGET`
  - 1) 의 11건이 **모두 머지 완료** → STOP REASON: `QUEUE_EMPTY`
  - 같은 이슈에서 **CI 실패가 3회 누적**되고 원인이 이 루프 범위 밖으로 판정됨 → STOP REASON: `CI_BLOCKED`
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 **누적 50회 도달** → STOP REASON: `TURN_CAP` (= or stop after 50 turns)

- **종료 방법** (순서대로 실행하고 각 출력을 대화에 남긴다):
  1. `docs/loop/CHECKPOINT.md` 마지막 줄에 `STOP REASON: <코드>` 한 줄을 덧붙인다.
  2. `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/python -m compileall -q src scripts tests` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  3. `npx tsc --noEmit -p tsconfig.json && npx vite build` 를 실행해 **exit 0** 출력을 대화에 남긴다.
  4. `grep -nE "^(CORE|MINOR|STOP REASON):" docs/loop/CHECKPOINT.md` 를 실행해 두 카운터 줄과 STOP REASON 줄이 보이는 출력을 대화에 남긴다.
  5. `gh issue list --state open --limit 100` 을 실행해 남은 열린 이슈 목록을 대화에 남긴다.
  6. `gh pr list --state merged --limit 15` 를 실행해 이 루프가 머지한 PR 목록을 대화에 남긴다.
  7. 아래 5) 의 판단 보류 항목을 **표 한 개**로 정리해 대화에 남긴다 (파일 수정 없이 보고만).

---

## 4) 기타 제약조건

- **금지 행동**:
  - `main` 에 직접 커밋·푸시 금지. 모든 변경은 `feature/issue-<N>-*` 브랜치 경유.
  - `--force` push 금지.
  - **CI 실패를 재실행으로 넘기지 않는다.** 플레이크로 판단되면 원인을 조사해 별도 이슈로 등록하고, 3회 연속 pass 를 확인한 뒤에만 넘어간다.
  - 신규 npm·pip 의존성 추가 금지. `.claude/CLAUDE.md` §4 의 사전 승인 목록 밖이면 추가하지 말고 CORE 로 기록한 뒤 우회 구현한다.
  - DEC-01~17 위반 금지. 위반을 발견하면 "미구현" 으로 강등하지 말고 CORE 로 등재한다 (재발 방지 3).

- **수정 금지 파일**:
  - `docs/10_CorpBrain_PRD_v1.0.md`, `docs/10_CorpBrain_PRD_v1.1_after_grill.md`
  - `docs/SRS_v1.1_after_grill_OPUS.md`, `docs/SRS-draft_v0.6_OPUS.md`
  - `docs/issues/ISSUE_LIST.md` (아래 5) 참조 — 갱신 필요성만 보고하고 직접 고치지 않는다)
  - `docs/loop/DECISION_LOG.md` (종료된 루프의 기록이다. 이 루프는 `CHECKPOINT.md` 를 쓴다)
  - `.claude/CLAUDE.md`, `.github/workflows/ci.yml`
  - 기존 `migrations/v001~v006_*.sql` (신규 마이그레이션 추가는 허용, 기존 파일 편집은 금지)

- **활성 범위 외 변경 금지**. 단 `docs/loop/CHECKPOINT.md` 와 `docs/goals/` 는 예외로 허용한다.

---

## 5) 판단 보류 항목 — 코드를 건드리지 않고 종료 보고에만 포함

아래는 **구현 문제가 아니라 규격·이슈 정리 판단**이 필요한 항목이다. 이 루프에서 **임의로 close 하거나 이슈 본문을 고치지 않는다.** 종료 시 표로 정리해 사용자에게 보고만 한다.

| 이슈 | 사안 | 보고할 내용 |
|---|---|---|
| #6 | ANA-FE-03 | AC S2 는 "완료 모달" 을 요구하나 `.claude/CLAUDE.md` §6 은 "폴링·에러는 논블로킹 Toast" 를 명시. 구현은 Toast 이며 상위 규격 우선. AC 정정 후 close 가 적절한지 |
| #64 | WS-FE-03 | AC S1 이 동기 생성 API 를 전제하나 DEC-04 로 비동기화되어 `SCAN_LIMIT_REACHED` 가 생성 시점이 아니라 폴링 중 발생. AC 정정 vs 생성 시점 사전 검사 추가 중 어느 쪽인지 |
| #68 | INF-CMD-03 | `ruff.toml` banned-api + CI Lint 스텝으로 실질 충족. #85 로 분리·해소됨. close 가능 여부 |
| #35, #36 | MOCK-001/002 | 프론트가 실 API 에 배선 완료(#91)되어 목 서버의 목적이 소멸한 것으로 보임. close 가능 여부 |
| #94 | 프론트 왕복 테스트 러너 | Vitest·jsdom 미도입이 확정 결정이므로 이 이슈는 그 결정과 충돌한다. 범위 재정의 필요 |
| #17 | DL-CMD-01 | 잔여: `deeplink_mappings` 키가 문장 인덱스가 아니라 청크 인덱스이며 `[:20]` 절단. 청크 21개 이상 폴더는 뒤쪽 딥링크 누락. 스키마·생성 로직 변경 수반이라 별도 판단 필요 |
| #30 | LLM-FE-01 | 잔여: `cloud_price_updated_at` 기준일·"추정" 표기 미구현(DEC-16). 값은 `App_Config` 에 시드되어 있어 UI 바인딩만 남음. 이 루프 범위에 넣을지 |
| #14 | APP-UI-01 | **Windows 호스트 필수.** 부품은 검증됐으나 `CorpBrain.exe` 로 조립해 실행한 적이 없다. 출하 전 반드시 필요한 단계이며 macOS 에서는 원리적으로 불가 |
| — | `docs/issues/ISSUE_LIST.md` | #38~#57 중 14건이 실제로는 CLOSED 인데 문서에는 OPEN 으로 남아 있다. 수정 금지 파일이므로 갱신 필요성만 보고 |
