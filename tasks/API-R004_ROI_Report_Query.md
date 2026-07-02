---
name: Feature Task
title: "[Feature] API-R004: GET /api/v1/reports/roi (ROI 리포트 조회 Query)"
labels: 'feature, priority:medium, api-core'
---

## 🎯 Summary
- 기능명: [API-R004] GET /api/v1/reports/roi (ROI 리포트 조회 Query)
- 목적: B2B 도입 검토자(팀장 이상)에게 서비스 도입 후 누적된 자동화 처리 건수를 바탕으로 환산된 절감 시간과 인건비(ROI) 데이터를 집계하여 반환한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.6 (REQ-FUNC-024, REQ-FUNC-025), §6.1 API Endpoint

## 📝 Task Breakdown
- [ ] AUTH-002 미들웨어를 적용하여 호출자가 `Manager` 이상의 권한을 가졌는지 검증.
- [ ] DB에서 해당 `workspace_id`의 `approval_status = 'approved'` 상태인 초안 건수를 카운팅하고, 시스템 처리 로그(또는 Webhook 이벤트 처리량)를 집계하는 집계 함수(Aggregation 쿼리) 작성.
- [ ] 비즈니스 로직 적용: (예) 1건 승인 완료 시 절감 시간 = 60분 으로 상정하여 총 `saved_minutes` 및 임의의 환산 기준(예: 시급)에 따른 `saved_cost_krw` 계산.
- [ ] 성능 최적화를 위해 실시간 전체 테이블 집계 대신, 하루 단위로 캐싱된 통계 뷰(Materialized View 또는 Redis Cache)를 조회하도록 설계.

## ✅ Acceptance Criteria (BDD)
- **Given**: 권한이 'Manager'인 사용자가 ROI 대시보드 탭에 접속했을 때
- **When**: `GET /api/v1/reports/roi` 엔드포인트를 호출하면
- **Then**: HTTP `200 OK` 응답과 함께 `{ saved_minutes: 600, saved_cost_krw: 500000, roi_multiplier: 12.5 }` 형태의 정량화된 지표가 포함된 응답이 1초 이내(REQ-NF-003)에 반환되어야 한다.
- **When**: 'User' 권한 클라이언트가 접근 시
- **Then**: `403 Forbidden` 접근 거부 에러가 반환되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 복잡한 COUNT 및 SUM 연산이 포함되므로, 트랜잭션이 활발한 Primary DB에 부하를 주지 않도록 캐싱 계층(Redis)을 통과하는 구조를 강력히 권장한다.
