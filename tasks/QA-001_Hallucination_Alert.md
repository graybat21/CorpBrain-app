---
name: Feature Task
title: "[Feature] QA-001: 환각률 프록시 모니터링 Alert 로직"
labels: 'feature, priority:medium, qa'
---

## 🎯 Summary
- 기능명: [QA-001] 환각률 프록시 모니터링 Alert 로직
- 목적: LLM 환각(Hallucination) 발생률을 직접 측정하기 어려우므로, 프록시 지표인 '실무자 수정 빈도'를 모니터링하여 급증 시 자동 경고를 발생시키는 운영 로직을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.4 REQ-NF-019
- 선행 태스크: INF-004 (모니터링 시스템), API-W003 (승인/수정/반려 Command)

## 📝 Task Breakdown
- [ ] API-W003의 '수정 요청(revision)' 이벤트 발생 시 수정 횟수를 시계열 메트릭(Prometheus Counter 또는 Datadog Custom Metric)으로 적재하는 로직 구현.
- [ ] 슬라이딩 윈도우(24시간) 기준 수정 빈도의 이동 평균 계산 쿼리(PromQL 또는 Datadog Metric Query) 작성.
- [ ] 수정 빈도가 이동 평균 대비 1.5배 이상 급증 시 Warning Alert 발동 규칙 구성.
- [ ] Alert 발동 시 PagerDuty(INF-007) 또는 Slack Webhook 채널로 자동 알림 전송.
- [ ] Grafana 대시보드에 '환각 프록시 지표' 패널 추가: 수정 빈도 트렌드 그래프 + Alert 이력 표시.

## ✅ Acceptance Criteria (BDD)
- **Given**: 정상 상태에서 일평균 수정 요청이 10건인 워크스페이스에서
- **When**: 특정일에 수정 요청이 16건(1.5배 이상)으로 급증하면
- **Then**: 모니터링 시스템이 Warning Alert를 발동하고, 지정된 Slack 채널에 "환각 의심: 수정 빈도 1.6x 급증" 메시지가 전송되어야 한다.

## 🛡️ Constraints (NFRs)
- 운영 제약: Alert 오탐(False Positive)을 방지하기 위해, 워크스페이스 생성 후 초기 30일간은 베이스라인 수집 기간으로 Alert를 비활성화해야 한다.
