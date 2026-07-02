---
name: Feature Task
title: "[Feature] QA-002: 외부 API Rate Limit 소진율 80% Alert 로직"
labels: 'feature, priority:low, qa'
---

## 🎯 Summary
- 기능명: [QA-002] 외부 API Rate Limit 소진율 80% Alert 로직
- 목적: Slack/Jira 등 외부 API의 Rate Limit 할당량 소진이 80%에 도달하면 사전 경고를 발생시켜, 데이터 수집 파이프라인이 예기치 않게 중단되는 것을 방지한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.4 REQ-NF-020
- 선행 태스크: INF-004 (모니터링 시스템), ING-004 (Exponential Backoff)

## 📝 Task Breakdown
- [ ] ING-004(Exponential Backoff) 모듈에서 각 외부 API 호출 시 응답 헤더(`X-RateLimit-Remaining`, `X-RateLimit-Limit`)를 파싱하여 소진율 메트릭 적재.
- [ ] Prometheus Gauge 또는 Datadog Custom Metric으로 API별(Slack, Jira) Rate Limit 소진율(%) 시계열 데이터 기록.
- [ ] 소진율이 80%에 도달하면 Warning Alert 발동 규칙 구성, 95%에 도달하면 Critical Alert 발동.
- [ ] Alert 발동 시 PagerDuty(INF-007) 또는 Slack Webhook으로 "Slack API Rate Limit 80% 소진 — 수집 속도 조절 필요" 알림 전송.

## ✅ Acceptance Criteria (BDD)
- **Given**: Slack API의 분당 호출 제한이 100건이고, 현재 82건을 소진한 상태에서
- **When**: 모니터링 시스템이 1분 주기로 소진율을 체크하면
- **Then**: Warning Alert가 발동되고, "Slack API Rate Limit 82% 소진" 메시지가 운영 채널에 전송되어야 한다.

## 🛡️ Constraints (NFRs)
- 운영 제약: Alert 반복 발동(Alert Storm)을 방지하기 위해, 동일 API에 대한 경고는 최소 15분 간격(Cooldown)으로 제한해야 한다.
