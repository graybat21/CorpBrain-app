# CorpBrain Loop Checkpoint — P7 (Windows 검증)

CORE: 0

MINOR: 2

## 의사결정 기록

| # | 분류 | 트랙 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 2 | MINOR | W1 | `test_inf_cmd_02.py` 의 역분기(비-Windows) 테스트 2건의 `skipif` 사유 문자열에서 `DPAPI` 토큰 제거 — "no-DPAPI host behaviour" → "non-Windows secret-storage refusal branch" / "non-Windows key-clearing branch". 8개 Windows 전용 테스트는 이미 전부 PASS 라 구현 수정은 불필요했고, 이 변경은 W1 판정 기준("SKIPPED 목록에 DPAPI 문자열 0건")을 문자 그대로 충족시키고 미래 skip-list 감사의 오탐을 제거한다. 어서션·동작 무변경(문자열만). | skip 사유 문자열 워딩은 세 규격 문서에 근거 없음(MINOR 예시의 "네이밍/테스트 픽스처 구조"). |
| 1 | MINOR | W0 | `tests/test_issue_25.py` 의 두 벤치마크 하위프로세스 호출을 UTF-8 로 고정(`encoding="utf-8"` + `env PYTHONIOENCODING=utf-8`). cp949(한국어) 로케일 Windows 에서 `bench_scan.py` 의 em-dash(U+2014, `E2 80 94`) 출력을 `text=True` 가 ANSI 코드페이지로 디코딩하려다 리더 스레드가 죽어 `result.stdout is None` → `TypeError`. 벤치 스크립트 자체는 `returncode==0` 으로 정상. W0 pytest 게이트를 로컬 그린으로 만들기 위한 Windows 전용 테스트 경로 수정(수정 허용 예외 목록에 해당). | 하위프로세스 출력 인코딩 처리는 PRD·SRS·CLAUDE.md 어디에도 명시가 없다. CLAUDE.md §4 의 "Windows edge cases gracefully" 는 파일시스템 op 한정이라 테스트 하네스 인코딩에 직접 근거로 보기 애매 → 보수적으로 MINOR 계상. |
