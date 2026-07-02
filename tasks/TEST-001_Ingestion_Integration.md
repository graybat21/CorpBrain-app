---
name: Feature Task
title: "[Feature] TEST-001: 수집 파이프라인 Integration Test (TC-001~004)"
labels: 'feature, priority:high, test'
---

## 🎯 Summary
- 기능명: [TEST-001] 수집 파이프라인 Integration Test (TC-001~004)
- 목적: SRS §5.4에 정의된 TC-001~004 테스트 케이스를 자동화하여, Webhook 수신 → Redis 적재 → Slack/Jira 파싱 → Rate Limit 백오프까지의 Data Ingestion 파이프라인 전체를 통합 검증한다.

## 🔗 References (Spec & Context)
- SRS 문서: §5.4 TC-001~004
- 선행 태스크: ING-002 (Slack Events API), ING-003 (Jira Webhooks), ING-004 (Exponential Backoff)

## 📝 Task Breakdown
- [ ] TC-001: 유효한 Slack Webhook Payload 수신 → Redis Queue 적재 → DB 영구 저장까지 End-to-End 정상 흐름 검증.
- [ ] TC-002: 유효한 Jira Webhook Payload에 대해 동일한 정상 흐름 검증.
- [ ] TC-003: 잘못된 포맷(Missing required fields, Invalid JSON)의 Payload 수신 시 400 에러 반환 및 Redis 미적재 검증.
- [ ] TC-004: 외부 API Rate Limit 초과 시 ING-004 Exponential Backoff가 정상 동작하고, 재시도 후 최종 성공하는지 검증.
- [ ] 테스트 환경: Docker Compose 기반 PostgreSQL + Redis 컨테이너를 띄우고, 테스트 후 자동 정리(Teardown).

## ✅ Acceptance Criteria (BDD)
- **Given**: Docker 기반 테스트 환경에서 PostgreSQL + Redis가 기동된 상태에서
- **When**: `npm run test:integration:ingestion` 명령어를 실행하면
- **Then**: TC-001~004 전체가 Pass하고, 테스트 결과 리포트에 4건 모두 Green이 기록되어야 한다.

## 🛡️ Constraints (NFRs)
- 격리 제약: Integration Test는 실제 Slack/Jira API를 호출하지 않으며, Webhook Payload를 직접 주입(Inject)하는 방식으로 외부 의존성을 제거해야 한다.
