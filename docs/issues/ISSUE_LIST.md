# CorpBrain Issue List & Tracking Board

## 1. Issue Tracking Board

| Issue # | Type | Title | Status | Priority | Linked PR | Dependency | Note |
|---|---|---|---|---|---|---|---|
| #67 | PR | [Design Lock] DEC-01~DEC-17: 구현 착수 전 설계 결정 17건 확정 및 SRS/PRD/tasks/하네스 정합화 | MERGED | High | - | - | PRD v1.1, SRS v1.1 기준점 |
| #38 | Issue | [Feature] RN-CMD-02: 승인된 Diff 기반 OS 레벨 물리 파일 Rename 및 내역 확정 | CLOSED | High | - | [REQ-FUNC-016] AI 추천 (F3 심층분석 선행) | [REQ-FUNC-018] OS 파일명 변경 로직 |
| #39 | Issue | [Feature] RN-CMD-03: `Rename_History` 기록 기반 OS 파일명 100% 원복(Undo) 실행 | CLOSED | High | - | #38 (RN-CMD-02) | [REQ-FUNC-019] 롤백 처리 |
| #40 | Issue | [Feature] RN-FE-01: Rename Diff 미리보기 테이블 렌더링 | CLOSED | Medium | - | [REQ-FUNC-016] AI 추천 완료 | [REQ-FUNC-017] UI 렌더링 |
| #41 | Issue | [Feature] RN-FE-02: Apply 및 Undo 버튼 동작 및 실패 모달 렌더링 | CLOSED | High | - | #40 (RN-FE-01), #38, #39 | [REQ-FUNC-018, 019] 연동 |
| #42 | Issue | [Feature] RN-QRY-01: 생성된 파일명 Diff (Old/New) 매핑 리스트 반환 | CLOSED | Low | - | [REQ-FUNC-016] AI 추천 완료 | - |
| #43 | Issue | [Feature] RN-TEST-01: Rename Undo 100% 원복 통합 테스트 | CLOSED | High | - | #39 (RN-CMD-03) | - |
| #44 | Issue | [Feature] SCAN-CMD-01: 파일 트리 순회 및 블랙리스트 제외 후 `File_Meta` 벌크 Insert | CLOSED | High | - | [REQ-FUNC-001] Workspace 생성 선행 | [REQ-FUNC-005] 블랙리스트 적용 |
| #45 | Issue | [Feature] SCAN-CMD-02: 파일 수 10,000개 도달 시 순회 중단 및 Limit Guard 예외 반환 | CLOSED | Medium | - | #44 (SCAN-CMD-01) | [REQ-FUNC-004] 10K Guard |
| #46 | Issue | [Feature] SCAN-QRY-01: 스캔된 파일 수, 용량(MB), 예상 소요시간 산출 후 반환 | CLOSED | Low | - | #44 (SCAN-CMD-01) | [REQ-FUNC-003] 통계 표시 |
| #47 | Issue | [Feature] SCAN-TEST-01: 스캔 필터링(블랙리스트) 단위 테스트 | CLOSED | Medium | - | #44 (SCAN-CMD-01) | - |
| #48 | Issue | [Feature] SCAN-TEST-02: 스캔 Limit Guard (10K 제한) 단위 테스트 | CLOSED | Medium | - | #45 (SCAN-CMD-02) | - |
| #49 | Issue | [Feature] STAT-CMD-01: 통계 이벤트 발생 시 수치 로깅 및 DB Insert | CLOSED | Low | - | [F3] 심층분석, [F6] Watcher 선행 | [REQ-FUNC-027~030] 데이터 수집 |
| #50 | Issue | [Feature] STAT-FE-01: My Analytics 차트 및 4대 지표 대시보드 UI 렌더링 | CLOSED | Low | - | #51 (STAT-QRY-01) | [REQ-FUNC-027~030] 시각화 |
| #51 | Issue | [Feature] STAT-QRY-01: WPM 기반 통계 산출 | CLOSED | Low | - | #49 (STAT-CMD-01) | [REQ-FUNC-027] Time Saved 계산 |
| #52 | Issue | [Feature] STAT-TEST-01: WPM 기반 절약 시간 산출 단위 테스트 | CLOSED | Low | - | #51 (STAT-QRY-01) | - |
| #53 | Issue | [Feature] WA-CMD-01: Watcher 설정 모드(수동/실시간/유휴) 변경 및 DB 저장 | CLOSED | Low | - | - | [REQ-FUNC-023] 설정 저장 |
| #54 | Issue | [Feature] WA-CMD-02: `watchdog` 이벤트 감지, 디바운싱 및 타임스탬프 대조 로직 | CLOSED | High | - | [F1] 파일 스캔 및 DB 구축 선행 | [REQ-FUNC-024] 이벤트 감지 |
| #55 | Issue | [Feature] WA-CMD-03: 내용이 수정된 파일 재분석 및 위키 부분 재생성 후 DB 갱신 | CLOSED | High | - | #54 (WA-CMD-02), [F3] 파싱 모듈 | [REQ-FUNC-025] 백그라운드 갱신 |
| #56 | Issue | [Feature] WA-FE-01: UI 설정 콤보박스 및 상태 아이콘 렌더링 | CLOSED | Low | - | #53 (WA-CMD-01) | [REQ-FUNC-023] UI 렌더링 |
| #57 | Issue | [Feature] WA-FE-02: 백그라운드 위키 갱신 성공 시 IPC Toast 알림 렌더링 | CLOSED | Low | - | #55 (WA-CMD-03) | [REQ-FUNC-025] 알림 노출 |

## 2. 에이전트 의사결정 체크포인트

멀티에이전트 간 상태 공유 및 조기 종료 판단을 위한 누적 카운터입니다.

> **[판단 기준]**
> PRD와 SRS 두 문서 모두에 명시되지 않은 **'기획적 변경'**이나 **'중대한 기술 스택/아키텍처 변경'**만이 발생했을 때 누적 카운트로 산정합니다. (문서 내 이미 정의된 구현 디테일은 제외)

- **[Core] 핵심 의사결정 누적 (Limit: 3회 이상):** 0 / 3
- **[Minor] 부수적 의사결정 누적 (Limit: 10회 이상):** 0 / 10
