# 개발 환경 설정

CorpBrain 은 **Windows 전용 출하 제품**이다 (`DEC-01`: pywebview + WebView2, PyInstaller
`--onefile` → 단일 `CorpBrain.exe`). 그러나 개발은 macOS 에서도 가능해야 하므로, 이 문서는
"어떤 호스트에서 무엇이 돌아가고 무엇이 돌아가지 않는가"를 명시한다.

**핵심 원칙: 개발 호스트 호환은 출하 동작을 바꾸지 않는다.** Windows 전용 API 를 다른 것으로
대체하는 shim 은 `src/backend/utils/platform_compat.py` 한 곳에만 존재하며, 보안 통제를
약화시켜 호환을 얻지 않는다.

---

## 1. 백엔드 (Python 3.10+)

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip

# macOS
.venv/bin/python -m pip install -r requirements.lock.macos.txt

# Windows
.venv\Scripts\python -m pip install -r requirements.lock.windows.txt
```

락 파일이 **플랫폼별로 분리되어 있다.** 하나로 합칠 수 없다 — `pywebview` 가 Windows 에서는
`pythonnet`/`clr_loader` 를, macOS 에서는 `pyobjc-*` 를 끌어오므로 반대 플랫폼의 락은 설치 자체가
실패한다. 직접 의존성(`requirements.txt`)은 양쪽 공통이다.

### 검증 게이트 (PR 전 필수 — CLAUDE.md §5)

```bash
.venv/bin/python -m compileall -q src scripts tests   # 문법 (충돌 마커 포함)
.venv/bin/ruff check .                                # 린트 + DEC-15 금지 import
.venv/bin/python -m pytest -q                         # 테스트
```

세 게이트 모두 `.github/workflows/ci.yml` 에서 `windows-latest` / `macos-latest` 양쪽으로 돌며
머지를 차단한다. **CI 가 없던 동안 이 세 유형의 회귀가 각각 main 에 도달했다** — 커밋된 충돌
마커, `response_model` 누락 2건, `NetworkGuard` 밖의 `urllib.request` import.

### 실 HTTP 검증 (엔드포인트를 건드린 작업은 필수 — DECISION_LOG 재발방지 5)

```bash
.venv/bin/python -u scripts/dev_serve.py          # port=0, 토큰은 콘솔에만
.venv/bin/python -u scripts/dev_serve.py --open   # SPA 까지 브라우저로
```

단위 테스트 그린은 "라우트가 응답한다"를 뜻하지 않는다. 이슈 #90·#91 이 정확히 이 공백에서 나왔다.

## 2. 프론트엔드 (Node 22 / npm 10)

```bash
npm ci
npx tsc --noEmit -p tsconfig.json
npx vite build
```

Node 는 **빌드 타임 툴체인 전용**이다. 산출물은 정적 SPA 번들이며 PyInstaller `--add-data` 로
exe 에 박힌다. 출하 산출물에 Node 런타임은 들어가지 않는다 (`DEC-01`).

API 타입은 손으로 고치지 않는다. FastAPI 가 낸 OpenAPI 스키마가 계약 SSOT 이므로 (`DEC-02`),
라우트를 바꿨으면 재생성한다:

```bash
.venv/bin/python scripts/gen_api_types.py           # src/frontend/api/types.gen.ts 갱신
.venv/bin/python scripts/gen_api_types.py --check    # CI 와 동일한 드리프트 검사
```

---

## 3. macOS 에서 다르게 동작하는 것

| 영역 | Windows (출하) | macOS (개발) | 근거 |
|---|---|---|---|
| 데이터 디렉터리 | `%LocalAppData%\CorpBrain\` | `~/Library/Application Support/CorpBrain/` | `platform_compat.get_local_app_data_dir()` |
| 딥링크 파일 열기 | `os.startfile` | `open` (실제로 열린다) | `platform_compat.open_with_default_app()` |
| API 키 저장 | DPAPI 암호화 → `App_Config` | **저장 불가 — 명시적 에러** | `DEC-12` |
| `MAX_PATH` / `\\?\` 접두 | 적용 | 해당 없음 (가드로 미적용) | `file_utils.normalize_path()` |

`LOCALAPPDATA` 환경변수는 모든 호스트에서 우선한다 — 테스트가 `monkeypatch.setenv` 로
임시 디렉터리를 가리키는 방식이 어디서든 동작해야 하기 때문이다.

### API 키 (`DEC-12`) — 개발 중 Option A 사용법

DPAPI 는 크로스플랫폼 등가물이 없다. macOS 에서 `POST /api/v1/config/llm` 으로 키를 저장하려
하면 이유를 명시한 에러가 돌아온다. 개발 중 Option A 를 실제로 호출해야 하면 환경변수를 쓴다:

```bash
export CORPBRAIN_ANTHROPIC_API_KEY=sk-ant-...
```

이 값은 호출 직전 **인메모리로만** 읽히고 DB·로그·응답에 절대 기록되지 않는다.

> **base64 폴백을 되살리지 말 것.** 이전 `security.py` 에는 non-Windows 용
> `"MOCK_ENC:" + base64(plaintext)` 폴백이 있었다. "단위 테스트용"이라는 주석이 붙어 있었지만
> 테스트로 한정하는 장치가 없었고 `set_api_key` 가 어느 호스트에서든 이를 호출했다. 즉 macOS 에서
> 실제 키를 입력한 개발자는 **되돌릴 수 있는 키를 디스크에 썼다** — `DEC-12` 가 금지하는 평문
> 저장 그 자체다. 더 나쁜 점은 당시 `test_scenario_3_plaintext_key_absent_in_db` 가
> "저장값 != 원문" 만 검사해서 이 폴백을 **통과시켰다**는 것이다. 지금은 저장 블롭을 base64
> 디코딩해 원문이 복원되지 않는지까지 검사한다.

### 테스트 skip 정책

macOS 에서 `pytest -q` 는 **8건을 skip** 한다. 전부 Windows 전용 규격(DPAPI, `MAX_PATH`,
`\\?\` 접두)을 검증하는 테스트이며, CI 의 `windows-latest` 잡에서 실제로 실행된다.

skip 대신 **어디서나 통과하도록 단정을 약화시키지 않는다** — 그렇게 하면 규격을 검증하지 않는
테스트가 그린으로 남는다. macOS 쪽에는 대신 그 호스트에서 성립해야 하는 속성을 별도로 고정한다
(예: `\\?\` 접두가 붙지 *않는다*, 키 저장이 *거부된다*).

---

## 4. 출하 빌드는 Windows 에서만

`CorpBrain.exe` 는 Windows 호스트에서만 만들 수 있다. macOS 의 PyInstaller 는 macOS 바이너리를
낸다. 릴리스 빌드 절차는 이슈 #14 (APP-UI-01: pywebview 셸 + `.spec`) 소관이며 아직 미구현이다.
