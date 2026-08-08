# 이슈 상태 재검증 (2026-08-08)

**기준**: `docs/review/CLOSED_ISSUE_AUDIT.md`(2026-08-07) 이후 머지된 PR #95~#104 반영
**방법**: 이슈 본문의 Acceptance Criteria(GWT)를 **한 항목씩** 코드와 대조. 이슈 제목·라벨·감사 문서의 이전 판정을 신뢰하지 않음
**대상**: 감사에서 재오픈/잔여추적 대상으로 지목된 이슈 + 프론트 이슈 전체

## 왜 다시 검증했는가

전날 감사는 **PR #95(프론트엔드 IPC 배선) 머지 이전** 시점이다. 그 PR 이 프론트 5개 페이지에 실 API 호출을 배선했으므로, 감사가 **FAKE**(목 데이터 렌더링)로 판정한 프론트 이슈들의 근거가 바뀌었다. 반대로 "배선되었으니 완료"라고 뭉뚱그리면 CLOSED_ISSUE_AUDIT 이 고발한 오판을 반복하게 된다 — 그래서 AC 를 한 줄씩 대조했다.

---

## 1. 결과 요약

| 조치 | 건수 | 이슈 |
|---|---|---|
| **CLOSE** | 2 | #23, #41 |
| **PARTIAL 유지** (잔여 명시) | 5 | #4, #17, #30, #40, #64 |
| **판단 요청** | 1 | #6 (규격 충돌) |
| **신규 등록** | 1 | #105 (다중 폴더 병합 미동작) |
| **PR 머지 시 자동 close** | 1 | #85 (PR #104 본문 `Closes #85`) |

**초기 판정을 정정했다.** 코드 배선 여부만으로 1차 훑었을 때 "7건 close 가능"으로 봤으나, AC 를 항목별로 대조하니 **실제 close 가능한 것은 2건**이었다. 나머지 5건은 핵심 경로는 있으나 특정 Scenario 가 비어 있다.

---

## 2. CLOSE (2건)

### #23 INF-CMD-01 — 글로벌 예외 처리

감사 판정(§6)은 "부분 — 글로벌 예외 처리기 미부착, 유틸은 완료"였다. **그 잔여가 해소되었다.**

- `api/app.py:69` `_install_exception_handlers()` → `:213` 등록. 핸들러 4건:
  `StarletteHTTPException`(상태코드→DEC-03 코드), `RequestValidationError`(Pydantic `input` 이 API 키를 되돌리는 것 차단 — DEC-12), `Exception`(트레이스백은 로컬 로그, 응답은 코드만), `EmbeddingModelChangedError`→409
- AC S1(권한 거부): `utils/file_utils.py:49` `safe_file_access` + `test_inf_cmd_01.py` 2건
- AC S2(MAX_PATH): `file_utils.py:10` `normalize_path` + `test_inf_cmd_01.py` 3건

**검증 환경 한정 사항**: MAX_PATH 테스트 3건은 Windows 에서만 실행된다. macOS 에서 `os.path.abspath("C:\\...")` 는 상대 경로로 취급해 CWD 를 붙이므로 단정이 규격을 검증하지 못한다. 단정을 약화시키는 대신 skip 하고 **CI 의 `windows-latest` 잡이 실제로 실행**한다 (Windows 205 passed / macOS 202 passed 의 차이).

### #41 RN-FE-02 — Apply/Undo 버튼

AC S1 충족. `RenamePage.tsx:56` `applyRename`, `:93` `undoRename`(둘 다 202+폴링), `:142` `animate-spin`, 성공 후 diff 소진 처리, `:55` 경로 미전송(DEC-08).

**잔여는 #39 소관으로 이관**: 프론트는 `ALREADY_UNDONE` 을 기대하지만 백엔드에 그 코드가 없다(`grep -rn ALREADY_UNDONE src/backend/` → 0건). 따라서 이 분기는 현재 도달하지 않는다.

---

## 3. PARTIAL 유지 (5건)

| 이슈 | 충족 | **잔여** |
|---|---|---|
| **#4** ANA-FE-01 | 실 API 호출, 중요도 배지 3단 색상(`FilesPage.tsx:205-212`), Empty State(`:234`) | ⓐ **중요도 내림차순 정렬 없음** — `sort` 0건이고 백엔드도 `file_repository.py:53` `ORDER BY file_name ASC` → **화면이 파일명 사전순**이다. AC S1("기획서가 상단에")과 정면 충돌. ⓑ 가상 스크롤 미적용(신규 의존성 검토 필요) |
| **#17** DL-CMD-01 | `deeplink_mappings` write 실재(`wiki_service.py:280,288`), 매핑 값이 `file_id` 뿐 | ⓐ **AC S2(경로 미포함) 검증 테스트 0건** — DEC-08 핵심 불변식이 회귀 테스트 없이 남아 있다. ⓑ 매핑 키가 문장 인덱스가 아니라 **청크 인덱스이며 `[:20]` 절단**(`wiki_service.py:262`) → 청크 21개 이상 폴더는 뒤쪽 딥링크가 조용히 누락 |
| **#30** LLM-FE-01 | health 13건 렌더링(감사 당시 0건), 4개 상태 분리 표시, `api_key_configured` 불리언만 노출 | **AC S2 미구현** — `cloud_price_updated_at`·"기준일"·"추정" 렌더링 0건. DEC-16 이 요구하는 단가 기준일 병기와 추정치 명시가 없다. 값은 `App_Config` 에 시드되어 있어 UI 바인딩만 남음 |
| **#40** RN-FE-01 | AC S1(테이블, old rose/new emerald), **AC S3(PII 행 제외 + "수동 확인 필요", DEC-17) 규격대로 구현**(`:9,160-161`) | **AC S2(개별 승인/거부) 미구현** — 체크박스 0건. 정상 추천 건을 골라 거부할 수단이 없다. `POST /rename/apply` 가 `history_id` 만 받으므로 **DTO 변경 수반**(→ `types.gen.ts` 재생성) |
| **#64** WS-FE-03 | 대시보드 실 바인딩(`DashboardPage.tsx:23`), 오류 Toast(`:31`, `CreateWorkspaceModal.tsx:65`) | **AC S1 이 구현과 어긋난다** — AC 는 "생성 버튼 클릭 시 10K 초과 → 다이얼로그 + 생성 상태 초기화"인데 `SCAN_LIMIT_REACHED` 는 생성 시점이 아니라 **DEC-04 폴링 중**에 발생한다. AC 가 동기 생성 API 를 전제로 쓰였고 이후 비동기화되며 어긋난 것. AC 정정 vs 생성 시점 사전 검사 추가가 설계 판단 |

---

## 4. 판단 요청 (1건)

### #6 ANA-FE-03 — AC 와 상위 규격의 충돌

AC S1 은 전부 충족한다: 1초 폴링(`client.ts:307` `sleep(1000)`), `N/M`+퍼센트 바(`FilesPage.tsx:146,152`), ETA(`:155`), 완료 시 폴링 중단(`client.ts:292`). WebSocket/SSE 0건(DEC-04).

**AC S2 는 "완료 모달"을 요구하지만 구현은 Toast** (`FilesPage.tsx:92`). 이는 누락이 아니라 상위 규격 우선 적용이다 — `.claude/CLAUDE.md` §6 이 "폴링 태스크와 에러는 전체 화면 모달이 아니라 논블로킹 Toast" 를 명시하며, `:138` 에 근거가 주석으로 남아 있다.

**선택지**: (a) Toast 로 충족 처리하고 close, (b) AC 문구를 CLAUDE.md 에 맞춰 정정한 뒤 close. 재발방지 3 의 취지에 따라 임의로 체크박스를 채우지 않는다.

---

## 5. 신규 등록 (1건)

### #105 — 다중 폴더 병합 미동작 (PRD 핵심 기능)

`scripts/dev_serve.py` 실 HTTP 호출로 실측했다. `root_paths` 2개를 보내면 `root_path` 1개만 저장되고, 스캔이 첫 폴더만 순회해 **두 번째 폴더의 파일이 오류도 경고도 없이 누락**된다.

감사 §4 가 #61 을 PARTIAL 로 판정하며 같은 사안을 지적했으나(`root_paths[0]` 만 저장), #61 은 이미 CLOSED 이고 이 결함은 스키마 변경(`Workspace_Meta.root_path` 단일 컬럼)을 수반하므로 별도 이슈로 분리했다. #66(WS-TEST-01)과 함께 처리하는 것이 효율적이다.

**이 결함은 단위 테스트 전량 그린과 공존했고 실 HTTP 호출로만 드러났다** — DECISION_LOG 재발방지 5 의 사례가 하나 더 늘었다.

---

## 6. 감사 문서 대비 변동

`CLOSED_ISSUE_AUDIT.md` §7 의 권고 대비 진행 상황:

| 감사 권고 | 현재 |
|---|---|
| 재오픈 9건 (#3·#4·#5·#7·#8·#9·#10·#37·#29) | #3·#7·#8 **해소**(PR #99·#101·#93). #5 해소(PR #102). #4 PARTIAL. #9·#10·#29·#37 **미착수** |
| close 4건 (#11·#13·#15·#27) | 전부 CLOSED |
| OPEN 유지 5건 (#39·#23·#17·#24·#16) | #23 **CLOSE**. #16 해소(PR #92). #39·#17·#24 잔여 유지 |
| 신규 이슈 2건 (#68 후속, DEC-11 위반) | #85(→PR #104 에서 해소), #84(→PR #97 에서 해소) |
| 등급 정정 2건 (#68, #30) | #68 → #85 로 분리 후 해소. #30 PARTIAL 확인 |

**추가로 CI 가 신설되어**(PR #104) 감사가 지적한 "린트를 강제할 정적 검사 부재"가 해소되었다. 첫 CI 실행이 실제 회귀 3건을 잡았다: `/wiki/generate`·`/reembed` 의 `response_model` 누락, `types.gen.ts` 드리프트, Python 3.12 전용 `numpy` 핀.

---

## 부록. GitHub Projects 보드 반영 상태

이슈 레이어(close/label/comment)만 갱신했다. **Projects V2 보드의 Status 필드는 반영하지 못했다** — 현재 `gh` 토큰에 `read:project`/`project` 스코프가 없어 `projectsV2` GraphQL 필드 호출이 `INSUFFICIENT_SCOPES` 로 거부된다.

레포에 auto-add 워크플로가 없으므로(`.github/workflows/` 에는 `ci.yml` 만 존재) **보드 카드 이동은 수동 또는 스코프 추가 후 처리가 필요하다**:

```bash
gh auth refresh -s project    # 브라우저 인증 1회
```

`06_Auto_Add_Workflow_필터_오류분석_및_교정_안내.md` 가 auto-add 워크플로 이슈를 다루고 있으나 해당 워크플로 파일은 리포에 없다.
