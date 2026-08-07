---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] STAT-QRY-01: WPM 기반 통계 산출"
labels: 'feature, backend, priority:low'
assignees: ''
---

## :dart: Summary
- 기능명: [STAT-QRY-01] 대시보드 통계 집계 (Query)
- 목적: 로깅된 액션과 추출된 문서량을 기반으로 '시간 절약(Time Saved)' 및 '압축률' 지표를 계산하여 프론트엔드로 반환한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-027, 029`
- **확정 사항: `DEC-07`** — 지표별 산출 소스 분리 (압축률만 스냅샷)

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 절약 시간: `Analytics_Log`에서 `SUM(tokens_processed) ÷ (250 WPM × 1.3 token/word)` → 분(min). **기간 필터(`?period`) 적용**
- [ ] **압축률: `COUNT(File_Meta WHERE parse_status='parsed') : COUNT(Wiki_Content)`** 로 산정한다. "토큰 대비 토큰" 비율이 아니며, **기간 필터를 적용하지 않는 현재 스냅샷 지표**다 (`DEC-07`)
- [ ] 딥링크 클릭 수(`event_type='deeplink_click'`), 워처 갱신 수(`event_type='watcher_update'`) COUNT 쿼리 작성 및 DTO 반환 (기간 필터 적용)
- [ ] 응답에 `knowledge_ratio_scope: "current"` 를 포함하여 압축률이 기간 무관 지표임을 명시
- [ ] **기간 경계는 프론트엔드가 로컬 타임존(KST) 기준으로 계산해 보낸 `from`/`to`(ISO-8601 UTC)를 그대로 비교한다** (`DEC-11`). 백엔드가 `week`라는 단어로 주 경계를 추정하지 않는다 — DB의 시각은 전부 UTC이므로 서버가 추정하면 KST 기준 "이번 주"와 최대 9시간 어긋난다

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 올바른 WPM 계산
- Given: 총 추출된 텍스트 볼륨이 250,000 단어임
- When: 대시보드 통계를 조회함
- Then: 절약된 시간 필드가 '1,000분' (혹은 환산된 시간)으로 반환된다.

## :construction: Dependencies & Blockers
- Depends on: STAT-CMD-01
- Blocks: STAT-FE-01
