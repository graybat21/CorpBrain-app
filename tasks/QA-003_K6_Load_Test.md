---
name: Feature Task
title: "[Feature] QA-003: 부하 테스트(k6/Locust) 시나리오 스크립트 작성 및 실행"
labels: 'feature, priority:medium, qa'
---

## 🎯 Summary
- 기능명: [QA-003] 부하 테스트(k6/Locust) 시나리오 스크립트 작성 및 실행
- 목적: 피크 타임에 대량의 Webhook 이벤트와 초안 생성 요청이 동시에 발생하는 상황을 시뮬레이션하여, 시스템의 안정성과 응답 시간 SLA 준수 여부를 검증한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.6 REQ-NF-023, REQ-NF-024
- 선행 태스크: API-W001 (초안 생성 Command), API-W003 (승인/수정/반려 Command)

## 📝 Task Breakdown
- [ ] Grafana K6 스크립트(`load-test.js`) 작성: 10,000건의 가상 Webhook Payload(Slack 포맷)를 `/webhook/slack` 엔드포인트로 전송하는 시나리오.
- [ ] 초안 생성 API(API-W001) 동시 호출 시나리오: 100명의 동시 사용자가 각각 초안 생성을 요청하는 Ramp-up/Ramp-down 프로파일.
- [ ] 승인 플로우(API-W003) 혼합 시나리오: 읽기(API-R001/R002)와 쓰기(API-W003) 비율을 8:2로 설정한 현실적 부하 패턴.
- [ ] 테스트 실행 중 서버 CPU, Memory, Redis Queue 길이를 Datadog/Grafana(INF-004)로 실시간 모니터링.
- [ ] K6 결과 리포트 분석: p95 Latency, Error Rate, Throughput 측정 및 SLA 대비 Pass/Fail 판정.

## ✅ Acceptance Criteria (BDD)
- **Given**: 스테이징 환경이 프로덕션과 동일한 스펙으로 프로비저닝된 상태에서
- **When**: K6 스크립트를 통해 초당 500건 이상의 동시 Webhook 트래픽(총 10,000건)을 주입하면
- **Then**: 95% 이상의 요청(p95)이 2초 이내에 `200 OK` 응답을 받아야 한다.
- **Then**: Redis 인스턴스가 다운되거나 OOM 현상이 발생하지 않아야 한다.

## 🛡️ Constraints (NFRs)
- 운영 제약: 부하 테스트는 반드시 운영(Production)과 완전히 격리된 스테이징(Staging) 환경에서만 수행해야 한다.
