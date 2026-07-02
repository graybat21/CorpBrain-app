---
name: Feature Task
title: "[Feature] API-R001: GET /api/v1/drafts/{draft_id} (초안 상세 조회 Query)"
labels: 'feature, priority:high, api-core'
---

## 🎯 Summary
- 기능명: [API-R001] GET /api/v1/drafts/{draft_id} (초안 상세 조회 Query)
- 목적: 실무자가 대시보드 에디터에서 문서 초안을 검토할 수 있도록, 병합된 초안 본문(`merged_content`)과 딥링크 맵핑 객체(`deeplink_map`)를 포함한 상세 데이터를 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.3 (REQ-FUNC-010~012), §6.1 API Endpoint

## 📝 Task Breakdown
- [ ] 파라미터 `draft_id` 유효성 검증(UUID 포맷 등) 및 JWT 기반 인증/인가 미들웨어(AUTH-001) 연동.
- [ ] DB의 `SEMANTIC_DRAFT` 테이블에서 해당 레코드를 단건 조회(SELECT)하는 Repository 로직 작성.
- [ ] 조회 요청자의 `workspace_id`와 해당 초안의 `workspace_id`가 일치하는지 대조하는 테넌트 분리 보안 검증.
- [ ] 클라이언트에 응답할 DTO 구조 조립 (`draft_id`, `merged_content`, `deeplink_map`, `approval_status`, `edit_history`).
- [ ] 존재하지 않거나 권한이 없는 초안을 조회할 경우 404/403 에러 처리.

## ✅ Acceptance Criteria (BDD)
- **Given**: 유효한 토큰을 지닌 사용자가 대시보드의 특정 초안 카드를 클릭했을 때
- **When**: `GET /api/v1/drafts/{draft_id}` 엔드포인트로 데이터 조회를 요청하면
- **Then**: HTTP `200 OK` 응답과 함께 딥링크 매핑 정보가 온전히 포함된 초안 상세 데이터 객체를 반환해야 한다.
- **Then**: 타 워크스페이스의 초안 ID를 강제로 주입하여 호출할 경우, `403 Forbidden` (또는 보안상 `404 Not Found`) 에러가 반환되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 단순 단건 조회 쿼리이므로 인덱스를 활용하여 p95 응답 속도가 매우 빠르도록(예: < 100ms) 최적화해야 한다.
- 구조 제약: CQRS 원칙에 따라 이 엔드포인트에서는 데이터의 어떠한 상태 변경(UPDATE, INSERT)도 수행해서는 안 된다.
