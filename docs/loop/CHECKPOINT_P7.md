# CorpBrain Loop Checkpoint — P7 (Windows 검증)

CORE: 0

MINOR: 1

## 의사결정 기록

| # | 분류 | 트랙 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 1 | MINOR | W0 | `tests/test_issue_25.py` 의 두 벤치마크 하위프로세스 호출을 UTF-8 로 고정(`encoding="utf-8"` + `env PYTHONIOENCODING=utf-8`). cp949(한국어) 로케일 Windows 에서 `bench_scan.py` 의 em-dash(U+2014, `E2 80 94`) 출력을 `text=True` 가 ANSI 코드페이지로 디코딩하려다 리더 스레드가 죽어 `result.stdout is None` → `TypeError`. 벤치 스크립트 자체는 `returncode==0` 으로 정상. W0 pytest 게이트를 로컬 그린으로 만들기 위한 Windows 전용 테스트 경로 수정(수정 허용 예외 목록에 해당). | 하위프로세스 출력 인코딩 처리는 PRD·SRS·CLAUDE.md 어디에도 명시가 없다. CLAUDE.md §4 의 "Windows edge cases gracefully" 는 파일시스템 op 한정이라 테스트 하네스 인코딩에 직접 근거로 보기 애매 → 보수적으로 MINOR 계상. |
