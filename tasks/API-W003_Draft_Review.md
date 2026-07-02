---
name: Feature Task
title: "[Feature] API-W003: PATCH /api/v1/drafts/{draft_id}/review (승인/수정/반려 Command)"
labels: 'feature, priority:high, api-core'
---

## 🎯 Summary
- 기능명: [API-W003] PATCH /api/v1/drafts/{draft_id}/review (승인/수정/반려 Command)
- 목적: 실무자가 대시보드에서 초안을 검토 후 내리는 최종 결정(승인, 수정 후 승인, 반려)을 시스템에 반영하고 연동된 위키(Notion 등)로 발행하는 파이프라인을 트리거한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.5 (REQ-FUNC-020~023), §4.2.1 (REQ-NF-004), §6.1 API Endpoint

## 📝 Task Breakdown
- [ ] URL 파라미터 `draft_id` 및 Request Body(`action`, `edits`, `publish_to`) 유효성 검사.
- [ ] DB의 `SEMANTIC_DRAFT` 테이블에서 해당 `draft_id` 레코드의 `approval_status`를 업데이트(`approved` 또는 `rejected`).
- [ ] `action`이 `approved`(수정 포함)일 경우, `edits` 데이터를 파싱하여 AIE-004(RL 피드백 루프) 모듈로 비동기 전달.
- [ ] `publish_to`(Notion, Confluence 등)가 지정된 경우, 외부 위키 발행 API(EXT-001/002)를 동기/비동기 호출하여 `published_url` 확보.
- [ ] 최종 결과(성공 여부 및 URL)를 클라이언트에 반환하는 컨트롤러 로직 마무리.

## ✅ Acceptance Criteria (BDD)
- **Given**: 사용자가 대시보드에서 초안 일부를 교정한 뒤 '승인 및 위키 발행'을 요청했을 때
- **When**: `PATCH /api/v1/drafts/{draft_id}/review` 엔드포인트가 호출되면
- **Then**: DB의 상태가 `approved`로 변경되고 수정 이력이 백그라운드에서 적재되어야 한다.
- **Then**: 위키 시스템에 초안이 성공적으로 발행되고, 그 결과물 URL(`published_url`)이 응답 데이터에 포함되어야 한다. (승인 후 발행 완료 p95 지연시간 ≤ 3초, REQ-NF-004)

## 🛡️ Constraints (NFRs)
- 성능 제약: 외부 위키 API 호출 지연이 전체 트랜잭션을 락(Lock) 상태로 만들지 않도록, 타임아웃을 짧게 가져가거나 발행 전용 비동기 큐를 두는 것을 설계 시 고려해야 한다.
- 정합성 제약: 동일한 `draft_id`에 대해 여러 사용자가 동시에 승인/반려를 요청하는 동시성 이슈(Concurrency)를 방지하기 위해 Optimistic Lock 또는 트랜잭션 격리를 적용해야 한다.
