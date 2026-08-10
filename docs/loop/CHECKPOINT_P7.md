# CorpBrain Loop Checkpoint — P7 (Windows 검증)

CORE: 0

MINOR: 4

## 의사결정 기록

| # | 분류 | 트랙 | 결정 내용 | 세 문서에 근거가 없는 사유 |
|---|---|---|---|---|
| 4 | MINOR | W2 | `test_app_ui_01_shell.py::test_built_archive_carries_the_spa_and_every_migration` 의 CArchive TOC 항목을 구분자 무관하게 정규화(`name.replace("\\", "/")`). Windows PyInstaller 는 TOC 멤버명을 백슬래시(`dist\index.html`)로 내는데 테스트는 POSIX 슬래시(`dist/index.html`)를 단정해 실패. SPA·마이그레이션은 실제로 정상 번들됨(TOC 확인). 이 테스트는 exe 산출물이 있어야 실행되는데 macOS/CI 파이썬 잡은 exe 를 안 만들어 **Windows 에서 한 번도 실행된 적 없던** Windows 전용 경로. exe 를 처음 빌드한 W2 에서 표면화. | PyInstaller CArchive TOC 의 경로 구분자 규약은 세 문서에 명시 없음. CLAUDE.md §4 의 pathlib 지침은 경로 생성용이지 아카이브 멤버명 파싱용이 아님 → 보수적으로 MINOR 계상. |
| 3 | MINOR | W2 | `CorpBrain.spec` 에 가드된 `binaries` 글롭 추가 — `sys.base_prefix/Library/bin/*.dll`(존재할 때만). onefile exe 가 `ImportError: DLL load failed while importing pyexpat` 로 부팅 실패했는데, Anaconda 가 expat/openssl/ffi/lzma/sqlite 등을 `Library\bin` 의 loose DLL 로 배포하고 stdlib C-확장이 PATH 로 로드해 PyInstaller 정적 분석이 놓치기 때문. onedir→onefile 전환(b23a420) 때 빠진 글롭의 회귀. 이 수정은 W2 의 정의(exe 가 헤드리스로 부팅되어 `--check-only` exit 0)를 충족시키며 DEC-01("단일 exe, 크래시 없이")을 오히려 지킨다. 비-Anaconda 호스트에선 `Library\bin` 부재로 글롭이 비활성(호스트 무관). 신규 의존성 아님(expat 은 기존 stdlib 구성요소). | PyInstaller 번들 시 loose DLL 수집 방식은 PRD·SRS·CLAUDE.md 에 명시 없음. DEC-01 은 "단일 exe" 를 요구하나 그 패키징 세부(어떤 DLL 을 어떻게 수집)는 규정하지 않음 → 보수적으로 MINOR 계상. |
| 2 | MINOR | W1 | `test_inf_cmd_02.py` 의 역분기(비-Windows) 테스트 2건의 `skipif` 사유 문자열에서 `DPAPI` 토큰 제거 — "no-DPAPI host behaviour" → "non-Windows secret-storage refusal branch" / "non-Windows key-clearing branch". 8개 Windows 전용 테스트는 이미 전부 PASS 라 구현 수정은 불필요했고, 이 변경은 W1 판정 기준("SKIPPED 목록에 DPAPI 문자열 0건")을 문자 그대로 충족시키고 미래 skip-list 감사의 오탐을 제거한다. 어서션·동작 무변경(문자열만). | skip 사유 문자열 워딩은 세 규격 문서에 근거 없음(MINOR 예시의 "네이밍/테스트 픽스처 구조"). |
| 1 | MINOR | W0 | `tests/test_issue_25.py` 의 두 벤치마크 하위프로세스 호출을 UTF-8 로 고정(`encoding="utf-8"` + `env PYTHONIOENCODING=utf-8`). cp949(한국어) 로케일 Windows 에서 `bench_scan.py` 의 em-dash(U+2014, `E2 80 94`) 출력을 `text=True` 가 ANSI 코드페이지로 디코딩하려다 리더 스레드가 죽어 `result.stdout is None` → `TypeError`. 벤치 스크립트 자체는 `returncode==0` 으로 정상. W0 pytest 게이트를 로컬 그린으로 만들기 위한 Windows 전용 테스트 경로 수정(수정 허용 예외 목록에 해당). | 하위프로세스 출력 인코딩 처리는 PRD·SRS·CLAUDE.md 어디에도 명시가 없다. CLAUDE.md §4 의 "Windows edge cases gracefully" 는 파일시스템 op 한정이라 테스트 하네스 인코딩에 직접 근거로 보기 애매 → 보수적으로 MINOR 계상. |
