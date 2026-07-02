---
name: Feature Task
title: "[Feature] API-R002: GET /api/v1/drafts (초안 목록 조회 Query)"
labels: 'feature, priority:high, api-core'
---

## 🎯 Summary
- 기능명: [API-R002] GET /api/v1/drafts (초안 목록 조회 Query)
- 목적: 대시보드 메인 화면에서 실무자가 처리해야 할 문서 초안 리스트(Pending/Approved 상태 포함)를 페이징 처리하여 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: 대시보드 메인 화면 렌더링 필수 요구사항

## 📝 Task Breakdown
- [ ] Query Parameters(Query String) 파싱 로직 구현 (`page`, `limit`, `status`, `sort` 등).
- [ ] JWT 기반 인증 모듈(AUTH-001) 연동 및 해당 사용자의 `workspace_id` 추출.
- [ ] DB의 `SEMANTIC_DRAFT` 테이블에서 `workspace_id`를 기준으로 다건을 조회하고 페이지네이션(Offset/Limit 또는 Cursor 기반)을 적용하는 쿼리 작성.
- [ ] 목록 화면의 부하를 줄이기 위해 `merged_content` 전체가 아닌 요약(Snippet) 텍스트나 앞의 100자 정도만 반환하도록 DTO 최적화.
- [ ] 전체 아이템 수(`total_count`) 및 다음 페이지 여부(`has_next`) 등 페이징 메타데이터 조립.

## ✅ Acceptance Criteria (BDD)
- **Given**: 사용자가 HITL 대시보드 메인 화면에 진입할 때
- **When**: `GET /api/v1/drafts?status=pending&page=1` 엔드포인트를 호출하면
- **Then**: HTTP `200 OK` 응답과 함께 아직 승인되지 않은 초안들의 목록과 페이징 정보가 반환되어야 한다.
- **Then**: 반환되는 목록 데이터에는 초안의 전체 본문이 아닌 화면 렌더링에 필요한 요약 정보만 포함되어 페이로드 사이즈가 최적화되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 다건 조회이므로 `workspace_id` 및 `generated_at`(또는 `status`) 컬럼에 복합 인덱스가 적절히 설정되어 있어 Full Table Scan을 방지해야 한다.
