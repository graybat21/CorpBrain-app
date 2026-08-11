# CorpBrain Loop Checkpoint — P8 (열린 이슈 소진)

CORE: 0

MINOR: 1

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 1 | MINOR | #151 | 창 배경색 상수를 **`#0f172a`** 로 결정(이슈 본문이 제안한 `#020617`=slate-950 이 아님). 근거: 기동 시 **첫 페인트를 담당하는 것은 `index.html` 의 `<body class="bg-dark-bg">`** 이며(React 루트의 `bg-slate-950` 은 번들 마운트 후에야 그려진다), `bg-dark-bg` 는 `tailwind.config.js` 의 `dark.bg = '#0f172a'` 로 해석된다. 빌드 산출물 CSS 에서도 `rgb(15 23 42)` = `#0f172a` 로 확인. 상수를 `WINDOW_BACKGROUND_COLOR` 로 노출하고 tailwind 설정과의 동기화를 테스트로 고정했다. | 창 배경색 값은 PRD·SRS·CLAUDE.md 어디에도 명시가 없다(MINOR 예시의 "UI 디테일·상수값 선택"). |
