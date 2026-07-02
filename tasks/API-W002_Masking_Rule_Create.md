---
name: Feature Task
title: "[Feature] API-W002: POST /api/v1/masking-rules (마스킹 규칙 등록 Command)"
labels: 'feature, priority:medium, api-core'
---

## 🎯 Summary
- 기능명: [API-W002] POST /api/v1/masking-rules (마스킹 규칙 등록 Command)
- 목적: 고객사 관리자가 커스텀 기밀 키워드나 정규식 규칙을 등록할 수 있는 기능을 제공하여 시스템의 동적 보안 정책을 강화한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.4 (REQ-FUNC-018), §6.1 API Endpoint

## 📝 Task Breakdown
- [ ] Request Body(`workspace_id`, `rule_type`, `pattern`, `is_active`) 유효성 검증(Zod 등).
- [ ] AUTH-002(RBAC 미들웨어)를 연동하여 요청자가 `Admin` 권한을 가지고 있는지 검증.
- [ ] `MASKING_RULE` 테이블에 신규 규칙을 INSERT(또는 UPSERT) 하는 Repository 로직 구현.
- [ ] SEC-003(마스킹 동적 적용) 캐시 모듈에 무효화(Invalidation) 또는 갱신 이벤트를 발행(Pub/Sub)하여 파이프라인에 즉시 반영되도록 트리거링.

## ✅ Acceptance Criteria (BDD)
- **Given**: Admin 권한을 가진 사용자가 대시보드(APP-004)에서 "기밀프로젝트X"라는 키워드를 추가할 때
- **When**: `POST /api/v1/masking-rules` API가 호출되면
- **Then**: DB에 해당 규칙이 활성(is_active: true) 상태로 저장되고 `201 Created` 응답이 반환되어야 한다.
- **Then**: 1분 이내에 수집 파이프라인 캐시가 갱신되어 다음 이벤트부터 즉시 마스킹이 적용되어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 요청 Payload에 XSS 유발 스크립트나 위험한 정규식(ReDoS 공격 유발 패턴)이 포함되지 않았는지 철저한 Sanitization 처리가 요구된다.
