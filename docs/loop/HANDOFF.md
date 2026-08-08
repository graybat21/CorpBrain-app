  CorpBrain 인수인계 브리핑 (Opus 5 → Sonnet)

  1. 지금 상태 (2026-08-08 갱신) — 중단된 작업 없음

  | 항목 | 상태 |
  |---|---|
  | 머지 완료 | PR #95(#91 IPC 배선), #96~#103 — main = `c8ff9e5` |
  | 개발 호스트 | **Windows → macOS 로 이동.** 이슈 #104 PR 에서 해소 (아래 2절) |
  | CI | **신설됨** — `.github/workflows/ci.yml`, 이슈 #85 해소. windows/macos 양쪽 그린 |
  | PR #104 | open. macOS 개발 환경 + CI 게이트. 3잡 전부 pass |
  | 게이트 결과 | macOS 202 passed/8 skipped · Windows 205 passed/5 skipped · ruff 0 · tsc 0 · vite 0 |

  **CI 가 첫 실행에서 실제 회귀 3건을 잡았다** (그전까지 이 3건이 그대로 main 에 있었다):
  `/wiki/generate`·`/reembed` 의 `response_model` 누락, `types.gen.ts` 드리프트, 3.12 전용
  `numpy` 핀. 앞으로 로컬 게이트를 잊어도 머지가 차단된다.

  첫 행동 권장: PR #104 머지 확인 → `git checkout main && git pull` → 아래 4절.

  2. 환경 — **개발 호스트가 macOS 로 이동했다** (2026-08-08)

  전체 절차는 `docs/DEVELOPMENT.md` 가 SSOT 다. 아래는 요약이다.

  # macOS (현재 개발 호스트). Python 3.10 필수 — 3.12 로 만들면 락 재생성 시 깨진다
  python -m venv .venv   # 3.10 인터프리터로
  .venv/bin/python -m pip install -r requirements.lock.macos.txt

  .venv/bin/python -m pytest -q
  .venv/bin/ruff check .
  .venv/bin/python -m compileall -q src scripts tests
  .venv/bin/python -u scripts/dev_serve.py      # 실 HTTP 검증

  # 프론트 (Node v22 / npm 10) — 플랫폼 무관
  npm ci && npx tsc --noEmit -p tsconfig.json && npx vite build

  # Windows 에서 작업할 경우 (출하 빌드는 여기서만 가능)
  .venv\Scripts\python -m pip install -r requirements.lock.windows.txt
  # -X utf8 없으면 한국어 출력에서 UnicodeDecodeError

  **락 파일이 플랫폼별로 분리됐다.** `pywebview` 가 Windows 에선 `pythonnet`/`clr_loader`,
  macOS 에선 `pyobjc-*` 를 끌어오므로 하나로는 양쪽 설치가 불가능하다.

  **이제 CI 가 있다** (`.github/workflows/ci.yml`, 이슈 #85). `compileall` + `ruff` +
  `pytest` 를 `windows-latest`/`macos-latest` 양쪽으로 돌리고 `tsc`/`vite build` 를 더한다.
  로컬 게이트를 잊어도 머지가 차단된다. macOS 는 202 passed/8 skipped, Windows 는
  205 passed/5 skipped 가 정상이다 — 차이는 DPAPI·MAX_PATH 등 Windows 전용 규격 테스트다.

  시간을 잡아먹은 함정 9개:
  1. Python은 3.10 — f-string 표현식 안에 백슬래시 금지 (3.12+ 기능).
  2. Python의 /tmp는 C:\tmp, bash의 /tmp는 다른 곳. curl 바디 파일 등 양쪽이 같은 파일을 봐야 하면
  C:/tmp/...로 명시. (macOS 에서는 해당 없음)
  3. curl JSON 바디에 Windows 경로/한국어를 셸로 조립하면 깨진다 → 바디는 Python으로 파일에 쓰고
  --data-binary @/tmp/body.json.
  4. app.state 속성은 ws_service (workspace_service 아님).
  5. Windows 테스트 teardown 순서: app.state.task_runner.active_task_ids() 전부 wait → db_mgr.close()
  → TemporaryDirectory 해제. 어기면 PermissionError [WinError 32]. **단정 실패로 close() 에 도달하지
  못해도 같은 증상이 나며, 이때 진짜 원인(단정 실패)이 정리 트레이스백에 묻힌다** — close 는 finally
  또는 yield 픽스처로 보장할 것.
  6. 소스를 문자열로 스캔하는 테스트는 주석을 먼저 제거할 것 — 파일이 자기가 지키는 규칙을 문서화해
  놓으면 그 문서가 위반으로 잡힌다 (tests/test_ws_fe_01.py::_code() 참고).
  7. **`ConfigManager(config_path=...)` 는 그 경로의 *디렉터리*만 쓰고 DB 이름은 항상
  `corpbrain_meta.db` 다.** 한 tmpdir 안에 `config1.json`/`config2.json` 두 개를 만들면 **같은 DB** 다.
  export/import 왕복 테스트가 이 때문에 아무것도 검증하지 않고 통과하고 있었다. 서로 다른 디렉터리를
  쓰고, import 전 값을 반드시 단정할 것.
  8. **락 파일을 재생성할 땐 Python 3.10 venv 에서 해야 한다.** 3.12 에서 `pip freeze` 하면
  `numpy==2.5.x`(Requires-Python >=3.12) 가 박혀 CI 의 3.10 에서 설치 자체가 실패한다.
  9. macOS 에서 `patch("os.startfile")` 은 AttributeError 다 (속성이 없다). 딥링크는
  `src.backend.services.deeplink_service.open_with_default_app` 를 패치할 것.

  3. 절대 위반하면 안 되는 것 (새 세션이 가장 잘 어기는 순서)

  1. main에 직접 커밋/push 금지. 반드시 feature/issue-<번호>-<kebab> 브랜치 먼저.
  2. PR 본문에 Closes #<번호> 필수 (GitHub Projects 칸반 자동 전이 트리거).
  3. 이슈 close는 python scripts/github_task_tracker.py complete <TASK_ID> 경로만. 임의 일괄 close
  스크립트 금지 (close_completed_issues.py가 번호↔라벨 오류로 이슈 상태를 역전시킨 전례). 착수 시엔
  start <TASK_ID>. TASK_ID↔이슈 매핑은 scripts/github_task_tracker.py 상단 dict에 있다 (예: RN-QRY-01:
  42, WS-FE-01: 62).
  4. DECISION_LOG 재발방지 5: 엔드포인트를 추가·수정한 태스크는 scripts/dev_serve.py로 실제 HTTP 호출
  1회를 DoD 증거에 포함. 단위 테스트 그린은 "라우트가 응답한다"를 뜻하지 않는다 — #90과 #91이 정확히
  이 공백에서 나왔다.
  5. 재발방지 4: 목(mock)을 검증하는 테스트는 DoD 근거가 아니다. 기본값이 실경로를
  우회하면(network_guard=None 등) 그 테스트는 규격을 검증하지 못한다.
  6. DEC-01~17은 LOCKED. 의존성 추가 전 .claude/CLAUDE.md §4 금지 목록 확인 (SQLAlchemy, Electron,
  faiss/torch, WebSocket/SSE, openai, spacy, sentry 전부 금지).

  4. 다음 태스크 추천 — #29 (LLM-CMD-03 Ollama 프로비저닝)

  #90 은 해소됐다 (PR #96). 남은 것 중 가장 큰 공백이 #29 다.

  - **#29 LLM-CMD-03 프로비저닝 — 구현 0건.** `POST /api/v1/llm/onboard` 라우트 부재,
    `Async_Task.result_json.provision_mode` 부재, `assisted`/`detect_only` 분기 부재.
    `tests/test_llm_cmd_03.py` 는 파일명과 달리 DEC-16 재시도 정책을 검증하므로 이름으로 판단하면
    오판한다. DEC-13 을 정독할 것 — 폐쇄망에서 설치를 시도하면 규격 위반이다.
  - **#24 로그 로테이션 — `addHandler`/`basicConfig` 0건.** 즉 지금 모든 `logger.*` 호출이 어디에도
    남지 않는다. 크래시 진단 수단이 없다는 뜻이며, CLAUDE.md 의 "모든 예외는 컨텍스트와 함께 로깅"
    요구가 실질 미충족이다. 작업량 대비 효과가 가장 크다.
  - **#14 pywebview 셸 + PyInstaller `.spec` — 출하 산출물이 아직 존재하지 않는다.**
    DECISION_LOG CORE #4/#5 가 여기서만 완전히 해소된다. **Windows 호스트 필요.**
  - **#37 RN-CMD-01** — 추천값이 `f"2026-08_{name}"` 하드코딩. PII 게이트(DEC-17)는 실재하므로
    재구현 시 보존할 것.
  - **#39** `ALREADY_UNDONE` 에러코드 미구현 (프론트 RenamePage 는 이미 이 코드를 기대하고 있다).

  범위 밖에서 실측된 선행 결함 1건: `root_paths` 를 2개 보내도 `root_path` 1개만 저장되고 스캔이
  1개 폴더만 순회한다 (다중 폴더 병합 = PRD 핵심 기능 미동작). CLOSED_ISSUE_AUDIT §4 의 #61 후속
  지적과 일치한다. 스키마 변경(v00N 마이그레이션)이 필요하므로 별도 이슈로 다루는 편이 낫다.

  5. 재논의 불필요 — 이미 확정된 결정

  - 타입 생성: scripts/gen_api_types.py → src/frontend/api/types.gen.ts (Python 스크립트, 신규 npm
  의존성 없음). openapi-typescript 도입은 거부됨.
  - 프론트 테스트: Vitest / Testing Library / jsdom 도입하지 않음. pytest 계약 테스트만. 그 결과 #91의
  "최소 1개 페이지 왕복 테스트" AC는 미충족이며 #94로 이관됐다 — 체크박스를 소급해 채우지 말 것.
  - 루프 docs/goals/corpbrain-unblocked-batch.md는 2026-08-07 종료 (CORE_BUDGET_EXCEEDED 6/3). CORE
  1·2·3·6 RESOLVED, 4·5 MITIGATED(run_app.py 잔존). 종료된 루프의 카운터는 소급 조정하지 않는다.
  - **크로스플랫폼 shim 은 `src/backend/utils/platform_compat.py` 한 곳에만 둔다** (2026-08-08 확정).
  모듈마다 `sys.platform` 을 다시 분기하지 말 것 — 모든 SQL 이 Repository 에, 모든 egress 가
  NetworkGuard 에 있는 것과 같은 이유다.
  - **API 키에 non-Windows 폴백을 만들지 않는다** (DEC-12). 과거 `"MOCK_ENC:" + base64(plaintext)`
  폴백이 있었고 이는 평문 저장이었다. 개발 중 Option A 는 `CORPBRAIN_ANTHROPIC_API_KEY` 환경변수를
  인메모리로만 읽는다. macOS Keychain 도입은 검토 후 거부됨(출하에 쓰이지 않는 코드가 늘어난다).
  - **Windows 전용 규격 테스트는 skip 하고, 단정을 약화시키지 않는다.** 어디서나 통과하게 고치면
  규격을 검증하지 않는 테스트가 그린으로 남는다. macOS 쪽에는 그 호스트에서 성립해야 하는 속성을
  별도로 고정한다.