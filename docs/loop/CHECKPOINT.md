# CorpBrain Loop Checkpoint

CORE: 2
MINOR: 2

## 의사결정 기록

| # | 분류 | 이슈 | 결정 내용 | 근거 문서 부재 사유 |
|---|---|---|---|---|
| 3 | **CORE** | #50 | **Recharts 를 도입하지 않고** 압축률 시각화를 CSS/SVG 로 구현. 이슈 Task Breakdown 이 "Recharts 등 경량 차트 라이브러리" 를 명시하지만, `.claude/CLAUDE.md` §4 사전 승인 목록에 없는 신규 npm 런타임 의존성이다. 목표 문서 4) 가 "승인 목록 밖이면 추가하지 말고 CORE 로 기록한 뒤 우회 구현" 을 지시한다. | 이슈 본문(하위 문서)과 CLAUDE.md §4(상위 규격)의 **정면 충돌**이다. 상위 규격 우선 + PyInstaller 번들(DEC-01)에도 들어가므로 우회 구현을 택했다. 사용자 판단이 필요하면 종료 보고에 포함한다. |
| 4 | MINOR | #50 | 4대 지표의 DTO 필드 매핑: 팩트체크율 ← `deeplink_clicks_count`, 자동화 점수 ← `watcher_updates_count`. AC 는 지표 **이름**만 명시하고 어느 필드에서 오는지는 규정하지 않는다. | 매핑 선택이 세 문서 어디에도 없다. UI 레이블 수준의 판단이라 MINOR. |
| 2 | MINOR | #66 | `WorkspaceRepository.list_all` 의 `ORDER BY created_at DESC` 에 `rowid DESC` 2차 키를 추가. `strftime('%f')` 는 밀리초 해상도라 같은 밀리초에 생성된 워크스페이스들의 순서가 비결정적이며, 사이드바 목록이 동일 요청 두 번 사이에 재배치된다. | 정렬 2차 키 선택은 PRD·SRS·CLAUDE.md 어디에도 규정이 없다. 스키마 변경 없는 쿼리 수정이고 사용자에게 보이는 영향이 "목록 순서 안정성" 뿐이라 MINOR 로 계상한다. |
| 1 | **CORE** | #10 | `Wiki_Content.deeplink_mappings` 컬럼을 신설하는 마이그레이션 `v007` 추가. `wiki_service.py:280,288` 이 이 컬럼에 write 하지만 **어떤 마이그레이션에도 존재하지 않아 위키 생성이 100% `sqlite3.OperationalError` 로 실패**한다. | **스키마 변경**이므로 CORE 트리거에 해당(목표 문서 2-2). 컬럼의 이름·내용·제약은 CLAUDE.md DEC-08 이 이미 규정하므로 *설계 판단*은 없으나, 마이그레이션 추가 자체가 스키마 변경이고 재발방지 3 이 "위반을 미완성으로 강등 금지" 를 요구하므로 보수적으로 CORE 로 계상한다. |

## 진행 상황

루프 시작: 2026-08-10, main = `4afd0b6`

| 순번 | 이슈 | 태스크 ID | 상태 | PR |
|---|---|---|---|---|
| 1 | #47 | SCAN-TEST-01 | 완료 | #122 |
| 2 | #48 | SCAN-TEST-02 | 완료 | #123 |
| 3 | #9 | ANA-TEST-01 | 완료 | #124 |
| 4 | #10 | ANA-TEST-02 | 완료 | #125 |
| 5 | #22 | DL-TEST-01 | 완료 | #126 |
| 6 | #43 | RN-TEST-01 | 완료 | #127 |
| 7 | #34 | LLM-TEST-02 | 완료 | #128 |
| 8 | #66 | WS-TEST-01 | 완료 | #129 |
| 9 | #51 | STAT-QRY-01 | 완료 | #130 |
| 10 | #52 | STAT-TEST-01 | 완료 | #130 |
| 11 | #50 | STAT-FE-01 | 완료 | #131 |

STOP REASON: QUEUE_EMPTY
