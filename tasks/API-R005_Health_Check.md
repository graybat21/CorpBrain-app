---
name: Feature Task
title: "[Feature] API-R005: GET /api/v1/health (시스템 헬스체크 Query)"
labels: 'feature, priority:high, api-core'
---

## 🎯 Summary
- 기능명: [API-R005] GET /api/v1/health (시스템 헬스체크 Query)
- 목적: UptimeRobot, 로드밸런서(ALB) 및 Kubernetes 등 인프라 레벨의 모니터링 시스템이 애플리케이션의 정상 가동 상태를 지속적으로 확인할 수 있는 경량 엔드포인트를 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: §6.1 API Endpoint, §4.2.2 (REQ-NF-008)

## 📝 Task Breakdown
- [ ] JWT 인증 등 어떠한 미들웨어도 타지 않는 퍼블릭 라우팅 엔드포인트 구성.
- [ ] Primary DB(PostgreSQL)와의 연결 상태를 점검하는 매우 가벼운 핑(Ping) 쿼리(예: `SELECT 1`) 실행 로직 구현.
- [ ] Message Queue(Redis) 인스턴스와의 커넥션 상태 점검 로직 구현.
- [ ] 의존성 서비스들이 모두 정상일 경우 `200 OK` (상태: healthy) 반환, 하나라도 비정상일 경우 `503 Service Unavailable` 반환.

## ✅ Acceptance Criteria (BDD)
- **Given**: 외부 모니터링 에이전트(UptimeRobot)가 1분 간격으로 접근하는 상황에서
- **When**: `GET /api/v1/health`를 호출하면
- **Then**: 인증 절차 없이 즉시 시스템의 DB 및 캐시 연결 상태를 점검하고, 정상 시 `{ status: "healthy", timestamp: "...", version: "..." }` 포맷의 `200 OK` 응답을 밀리초 단위로 반환해야 한다.
- **Given**: 만약 DB 커넥션이 끊어졌거나 타임아웃이 발생했을 때
- **When**: 헬스체크를 호출하면
- **Then**: 즉각적으로 `503 Service Unavailable` 상태 코드 에러를 반환하여 모니터링 시스템이 다운타임을 감지할 수 있도록 해야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 모니터링 시스템이 1분 단위로 지속 호출하므로 응답 속도가 지연되어서는 안 되며, 핑 연산 외의 복잡한 로직은 배제해야 한다.
- 보안 제약: 시스템 버전이나 타임스탬프 외에 보안상 민감한 내부 에러 스택 트레이스나 IP 정보는 노출해서는 안 된다.
