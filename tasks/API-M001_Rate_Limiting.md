---
name: Feature Task
title: "[Feature] API-M001: 내부 API Rate Limiting 미들웨어"
labels: 'feature, priority:high, api-middleware'
---

## 🎯 Summary
- 기능명: [API-M001] 내부 API Rate Limiting 미들웨어
- 목적: 악의적인 DDoC 공격이나 비정상적인 대량 호출로부터 시스템 인프라 및 DB 자원을 보호하기 위해, 엔드포인트별로 허용된 호출 횟수(Rate Limit)를 제어하는 미들웨어를 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §6.1 API Endpoint List (Rate Limit 컬럼)

## 📝 Task Breakdown
- [ ] Redis 기반의 토큰 버킷(Token Bucket) 또는 슬라이딩 윈도우(Sliding Window) 알고리즘을 활용한 Rate Limit 유틸리티 작성.
- [ ] 전역 미들웨어(또는 인터셉터)를 구성하여 라우트별 허용치 적용:
  - `POST /api/v1/drafts/generate`: 10 req/min/workspace
  - `GET /api/v1/drafts/{draft_id}`: 60 req/min/user
  - 그 외 API 규격 참조.
- [ ] 토큰(JWT)에서 추출한 `user_id` 또는 `workspace_id`를 키(Key)로 사용하여 요청 건수를 카운팅.
- [ ] 초과 시 `429 Too Many Requests` 상태 코드 및 `Retry-After` 헤더를 포함한 표준 에러 응답 반환 로직 구현.

## ✅ Acceptance Criteria (BDD)
- **Given**: 동일한 워크스페이스 권한을 가진 사용자가
- **When**: 1분 이내에 11번째 `POST /api/v1/drafts/generate` (초안 생성) 요청을 시도하면
- **Then**: 요청이 거부되고 HTTP `429 Too Many Requests` 에러가 반환되어야 한다.
- **Then**: Redis 메모리에 기록된 카운트는 정확히 1분 뒤 만료(Reset)되어 재호출이 가능해져야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: Rate Limiting 체크 로직 자체가 병목이 되지 않도록 Redis와의 통신 지연을 5ms 이내로 최적화해야 한다.
