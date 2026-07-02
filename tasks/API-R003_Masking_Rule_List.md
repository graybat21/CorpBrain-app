---
name: Feature Task
title: "[Feature] API-R003: GET /api/v1/masking-rules (마스킹 규칙 목록 조회 Query)"
labels: 'feature, priority:medium, api-core'
---

## 🎯 Summary
- 기능명: [API-R003] GET /api/v1/masking-rules (마스킹 규칙 목록 조회 Query)
- 목적: 워크스페이스 관리자가 대시보드 내 '보안 설정' 메뉴에서 고객사에 등록된 전체 커스텀 마스킹 규칙 목록 및 활성화 상태를 조회할 수 있도록 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.4, APP-004 관리 화면 렌더링 필수 요소

## 📝 Task Breakdown
- [ ] AUTH-001(JWT) 및 AUTH-002(RBAC) 미들웨어를 연동하여 `Admin` 권한 검증.
- [ ] DB의 `MASKING_RULE` 테이블에서 요청자의 `workspace_id`에 속하는 모든 규칙을 조회하는 쿼리 작성 (생성일 역순 등 정렬).
- [ ] 활성(Active) 및 비활성(Inactive) 상태 필터링 쿼리 파라미터 옵션 지원 구현.
- [ ] 응답 DTO 구성 (`rule_id`, `rule_type`, `pattern`, `is_active`, `updated_at`).

## ✅ Acceptance Criteria (BDD)
- **Given**: Admin 권한을 가진 사용자가 보안 설정 화면에 접근할 때
- **When**: `GET /api/v1/masking-rules` 엔드포인트를 호출하면
- **Then**: 해당 고객사에 등록된 모든 마스킹 규칙 데이터 목록이 반환되어야 한다.
- **Given**: 일반 권한(User)의 실무자가 해당 엔드포인트를 호출하면
- **When**: 권한 부족으로 인해 `403 Forbidden` 에러 응답을 받아야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 정규식 패턴(pattern) 자체가 클라이언트 뷰에 그대로 렌더링되므로, API 응답 시 악의적인 XSS 스크립트가 인젝션되지 않았는지 데이터 무결성을 보장해야 한다.
