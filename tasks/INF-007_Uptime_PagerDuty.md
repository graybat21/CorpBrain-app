---
name: Feature Task
title: "[Feature] INF-007: UptimeRobot 헬스체크 및 PagerDuty Critical 알림 연동"
labels: 'feature, priority:high, infrastructure'
---

## 🎯 Summary
- 기능명: [INF-007] UptimeRobot 헬스체크 및 PagerDuty Critical 알림 연동
- 목적: 외부 합성 모니터링을 통한 SLA 99.9% 보장 및, 마스킹 실패와 같은 치명적인 보안 결함 발생 시 즉각적으로 담당자를 온콜(On-Call) 호출하기 위한 파이프라인을 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.2 (REQ-NF-008), §4.2.3 (REQ-NF-017)

## 📝 Task Breakdown
- [ ] API 서버의 `/api/v1/health` 엔드포인트를 UptimeRobot에 등록하고 1분 주기 외부 모니터링 설정.
- [ ] UptimeRobot 다운타임 감지 시 PagerDuty로 Webhook을 전송하도록 연동 구성.
- [ ] 시스템 로그(Datadog 등)에서 PII 마스킹 모듈 지연(>5초) 또는 마스킹 실패 로그가 1건이라도 탐지되면 PagerDuty Critical Alert를 트리거하는 알림 규칙 생성.
- [ ] PagerDuty 에스컬레이션 정책(Escalation Policy) 설정 및 엔지니어링팀 Slack 채널 양방향 연동.

## ✅ Acceptance Criteria (BDD)
- **Given**: 마스킹 모듈 처리 지연이 5초를 초과하거나 실패(에러)가 발생하는 상황에서
- **When**: 모니터링 시스템(Datadog/Grafana)이 이를 탐지하면
- **Then**: 즉시 PagerDuty Critical 알림이 트리거되어 온콜 담당자에게 전화/문자가 발송되고, 데이터 파이프라인 수집이 자동(또는 수동)으로 중단될 수 있도록 인지되어야 한다.
- **Then**: 외부 API 서버 다운 시 1분 이내에 UptimeRobot을 통해 담당자에게 알림이 도달해야 한다.

## 🛡️ Constraints (NFRs)
- 비즈니스 제약: 서비스 수준 합의(SLA) 99.9%를 모니터링하는 핵심 수단이므로, UptimeRobot 헬스체크 엔드포인트 자체는 인증 없이 매우 가볍게(DB 커넥션 여부 등 필수만) 응답해야 한다.
