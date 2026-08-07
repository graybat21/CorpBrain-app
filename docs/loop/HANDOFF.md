  CorpBrain 인수인계 브리핑 (Opus 5 → Sonnet)

  1. 지금 상태 — 중단된 작업 없음

  ┌─────────────────────────────┬─────────────────────────────────────────────────────────────────┐
  │            항목             │                              상태                               │
  ├─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ P4 = 프론트엔드 IPC 배선    │ 완료. 커밋 5ff38a9 (18 files, +1852/−177), 브랜치               │
  │ (#91)                       │ feature/issue-91-frontend-ipc-wiring push 완료                  │
  ├─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ PR #95                      │ open, 리뷰/머지 대기. 본문에 Closes #91 있음 → 머지 시 #91 자동 │
  │                             │  close                                                          │
  ├─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ 후속 이슈 #94               │ 신규 생성 (프론트 테스트 러너 부재 — #91이 못 채운 AC)          │
  ├─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ github_task_tracker.py      │ 실행 완료 → 이슈 #62 close                                      │
  │ complete WS-FE-01           │                                                                 │
  ├─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ 게이트 결과                 │ 175 passed / 1 skipped, ruff check . → All checks passed, tsc   │
  │                             │ --noEmit → 0, vite build → 0 (빌드 산출물에 외부 URL 0건)       │
  ├─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ 작업트리                    │ 깨끗함. untracked 파일들은 이 작업과 무관하며 의도적으로 그대로 │
  │                             │  뒀다 (run_app.py, 진행상황.md, 보고서 .md 3건, docs/goals/)    │
  └─────────────────────────────┴─────────────────────────────────────────────────────────────────┘

  첫 행동 권장: PR #95 머지 여부 확인 → 머지 후 git checkout main && git pull.

  2. 환경 — pytest도 ruff도 PATH에 없다

  이걸 모르면 첫 명령부터 막힌다. 전체 경로로 호출해야 한다.

  # 테스트 (-X utf8 없으면 한국어 출력에서 UnicodeDecodeError)
  C:/Users/docto/anaconda3/envs/corpbrain/python.exe -X utf8 -m pytest -q

  # 린트
  C:/Users/docto/anaconda3/envs/corpbrain/Scripts/ruff.exe check .

  # 프론트 (Node v22.14.0 / npm 10.9.2)
  npx tsc --noEmit -p tsconfig.json
  npx vite build

  # 실 HTTP 검증 서버 (-u 없으면 파이프로 넘길 때 배너가 flush 안 됨)
  C:/Users/docto/anaconda3/envs/corpbrain/python.exe -X utf8 -u scripts/dev_serve.py

  시간을 잡아먹은 함정 6개:
  1. Python은 3.10 — f-string 표현식 안에 백슬래시 금지 (3.12+ 기능).
  2. Python의 /tmp는 C:\tmp, bash의 /tmp는 다른 곳. curl 바디 파일 등 양쪽이 같은 파일을 봐야 하면
  C:/tmp/...로 명시.
  3. curl JSON 바디에 Windows 경로/한국어를 셸로 조립하면 깨진다 → 바디는 Python으로 파일에 쓰고
  --data-binary @C:/tmp/body.json.
  4. app.state 속성은 ws_service (workspace_service 아님).
  5. Windows 테스트 teardown 순서: app.state.task_runner.active_task_ids() 전부 wait → db_mgr.close()
  → TemporaryDirectory 해제. 어기면 PermissionError [WinError 32].
  6. 소스를 문자열로 스캔하는 테스트는 주석을 먼저 제거할 것 — 파일이 자기가 지키는 규칙을 문서화해
  놓으면 그 문서가 위반으로 잡힌다 (tests/test_ws_fe_01.py::_code() 참고).

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

  4. 다음 태스크 추천 — 이슈 #90 (GET .../rename/diff 100% 500)

  가장 강한 후보인 이유: 확정된 100% 실패 + 테스트 커버리지 0건이고, RenamePage의 GET 경로를 막고 있다
  (프론트가 지금 POST로 우회 중이며 코드에 그 사실이 주석으로 남아 있다).

  버그 2단이며 1단만 고치면 안 된다:
  - 원인 1 — src/backend/services/query_services.py:114-119가 Rename_History.status를 조회하는데 그
  컬럼이 스키마에 없다 (migrations/v001_initial_schema.sql:41-47). 실제 컬럼은 history_id,
  workspace_id, old_paths, new_paths, created_at. SELECT·WHERE·반환 dict 3곳에서 참조한다 →
  sqlite3.OperationalError: no such column: status.
  - 원인 2 — 컬럼을 고쳐도 안 된다. RenameService.process_rename_suggestions는 old_paths/new_paths를
  문자열 배열로 저장하는데 get_pending_rename_diff는 객체 배열로 읽는다 → AttributeError.

  주의할 규격: current_path만 쓰고 original_path는 절대 열지 않는다(DEC-08). 응답 봉투는 DEC-03.
  스키마에 status를 추가할지(마이그레이션 v00N) 아니면 조회를 컬럼 없이 재작성할지가 유일한 설계
  판단이며, 마이그레이션은 PRAGMA user_version 기반 + SQL은 Repository 안에만(DEC-05).

  DoD: 회귀 테스트 신설(현재 0건) + dev_serve.py 실 HTTP 호출 1회 + ruff 0. #90은 태스크 이슈가 아니라
  버그 이슈이므로 close는 PR 본문의 Closes #90으로 처리한다(tracker에 TASK_ID 없음).

  대안 후보: #84 (워처가 non-UUID file_id 할당 — DEC-11 위반), #89 (multi_status vs completed 봉투
  정합), #63 (WS-FE-02 워크스페이스 생성 모달), #14 (pywebview 셸 + run_app.py 삭제 = CORE #4/#5 최종
  해소), #7/#3 (위키 엔드포인트 — WikiPage가 여기서 막혀 있다).

  5. 재논의 불필요 — 이미 확정된 결정

  - 타입 생성: scripts/gen_api_types.py → src/frontend/api/types.gen.ts (Python 스크립트, 신규 npm
  의존성 없음). openapi-typescript 도입은 거부됨.
  - 프론트 테스트: Vitest / Testing Library / jsdom 도입하지 않음. pytest 계약 테스트만. 그 결과 #91의
  "최소 1개 페이지 왕복 테스트" AC는 미충족이며 #94로 이관됐다 — 체크박스를 소급해 채우지 말 것.
  - 루프 docs/goals/corpbrain-unblocked-batch.md는 2026-08-07 종료 (CORE_BUDGET_EXCEEDED 6/3). CORE
  1·2·3·6 RESOLVED, 4·5 MITIGATED(run_app.py 잔존). 종료된 루프의 카운터는 소급 조정하지 않는다.