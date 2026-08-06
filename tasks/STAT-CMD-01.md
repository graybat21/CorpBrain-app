---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] STAT-CMD-01: 통계 이벤트 발생 시 수치 로깅 및 DB Insert"
labels: 'feature, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [STAT-CMD-01] 사용자 액션 트래킹 (Command)
- 목적: "자동 문서 갱신(Watcher)", "딥링크 기반 빠른 열기" 등의 이벤트가 발생할 때마다 횟수 및 관련 로그를 DB에 적재하여, 추후 '절약 시간' 통계를 내기 위한 원천 데이터를 쌓는다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-028, 030`
- **확정 사항: `DEC-07`** — `Analytics_Log`에 `file_id`/`wiki_id` nullable FK 추가, 지표별 산출 소스 분리
- **확정 사항: `DEC-16`** — `cost_usd`는 실측 `usage` 토큰 × `App_Config` 단가(추정치). Option B는 `0`, 미측정은 `NULL`로 구분

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `Analytics_Log` 스키마는 SRS §6.2.5 확정본을 사용 (신규 컬럼 `file_id`, `wiki_id` 포함 / 인덱스 `(created_at)`, `(event_type, created_at)`)
- [ ] **`cost_usd` 기록 규칙 (`DEC-16`)**: Option A는 응답의 `usage.input_tokens`/`usage.output_tokens`와 `App_Config` 단가를 곱해 기록한다. **Option B(로컬)는 `0`** 을 기록하고, 호출 자체가 실패해 토큰을 알 수 없는 경우만 `NULL`로 둔다 — `0`("비용 없음")과 `NULL`("미측정")을 뒤섞지 않는다
- [ ] 단가를 코드에 하드코딩하지 않고 기록 시점에 `App_Config`에서 읽는다 (`DEC-12`·`DEC-16`)
- [ ] DL-CMD-02(딥링크 열기) 및 WA-CMD-03(위키 재생성) 완료 직후 통계 기록 트리거(로깅) 추가
- [ ] **`deeplink_click` 이벤트에는 `file_id`·`wiki_id`를 반드시 채운다** (다른 이벤트 유형은 NULL 허용)
- [ ] 비동기 Fire-and-Forget 방식으로 DB Insert 실행 (메인 비즈니스 로직 성능 저하 방지). 단 쓰기 트랜잭션은 짧게 유지 (`DEC-05`)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 딥링크 클릭 로깅
- Given: 백엔드 서버가 켜져 있음
- When: 딥링크 실행 커맨드가 정상적으로 처리됨
- Then: `Analytics_Log`에 `event_type='deeplink_click'`, `file_id`, `wiki_id`, `created_at`이 포함된 레코드가 성공적으로 적재된다.

Scenario 2: 원문 삭제 후 과거 집계 보존 (DEC-07)
- Given: `deeplink_click` 로그가 적재된 파일이 OS 상에서 삭제되어 `File_Meta` 레코드가 제거됨
- When: 팩트체크 횟수를 재집계함
- Then: `file_id`가 NULL로 전이될 뿐 로그 레코드는 유지되어, **과거 팩트체크 횟수가 소급 감소하지 않는다.**

> 주의: `event_type` 값은 소문자 스네이크(`deeplink_click`)로 통일한다. `DEEP_LINK_CLICK` 대문자 표기를 쓰지 않는다 (SRS §6.2.5).

## :construction: Dependencies & Blockers
- Depends on: DL-CMD-02, WA-CMD-03
- Blocks: STAT-QRY-01
