# CorpBrain Loop Checkpoint — P8 (열린 이슈 소진)

CORE: 0

MINOR: 2

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 2 | MINOR | #145 | 회귀 차단 수단으로 **`ci.yml` 로케일 매트릭스 대신 리포 차원 AST 가드 테스트**(`tests/test_issue_145.py`)를 선택. 이슈 본문이 제시한 두 선택지 중 후자다. 근거: (a) `ci.yml` 은 P8 수정 금지 파일이고 편집 시 CORE 소모, (b) 로케일 매트릭스는 실패를 *재현*만 할 뿐 새 호출 지점이 추가되면 다시 뚫리는데, AST 가드는 **모든 호출 지점을 호스트 무관하게 정적으로 강제**한다. 부수 발견으로 실제 위반 3건을 수정했다 — `provisioning_service.py:438`(**프로덕션 경로**, `ollama pull` 출력), `test_inf_test_02_telemetry.py` 2건. | 하위프로세스 인코딩 강제 수단(정적 가드 vs CI 매트릭스)의 선택은 PRD·SRS·CLAUDE.md 에 명시가 없다. ruff `banned-api`(DEC-15) 라는 정적 강제 선례는 있으나 이 규칙 자체의 근거는 아니므로 보수적으로 MINOR 계상. |
| 1 | MINOR | #151 | 창 배경색 상수를 **`#0f172a`** 로 결정(이슈 본문이 제안한 `#020617`=slate-950 이 아님). 근거: 기동 시 **첫 페인트를 담당하는 것은 `index.html` 의 `<body class="bg-dark-bg">`** 이며(React 루트의 `bg-slate-950` 은 번들 마운트 후에야 그려진다), `bg-dark-bg` 는 `tailwind.config.js` 의 `dark.bg = '#0f172a'` 로 해석된다. 빌드 산출물 CSS 에서도 `rgb(15 23 42)` = `#0f172a` 로 확인. 상수를 `WINDOW_BACKGROUND_COLOR` 로 노출하고 tailwind 설정과의 동기화를 테스트로 고정했다. | 창 배경색 값은 PRD·SRS·CLAUDE.md 어디에도 명시가 없다(MINOR 예시의 "UI 디테일·상수값 선택"). |

---

STOP REASON: QUEUE_EMPTY
