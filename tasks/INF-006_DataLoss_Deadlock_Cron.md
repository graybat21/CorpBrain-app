---
name: Feature Task
title: "[Feature] INF-006: 데이터 유실 대조 및 Deadlock 탐지 자동화 크론 스크립트"
labels: 'feature, priority:medium, infrastructure'
---

## 🎯 Summary
- 기능명: [INF-006] 데이터 유실 대조 및 Deadlock 탐지 자동화 크론 스크립트
- 목적: 다중 채널 수집 과정에서의 데이터 유실률 0%와 교착상태(Deadlock) 0% 유지를 위해 시스템의 건강 상태를 주기적으로 감시하고 자동으로 리포팅하는 스크립트를 구성한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.2 (REQ-NF-007, REQ-NF-009)

## 📝 Task Breakdown
- [ ] Redis Message Queue에 진입한 이벤트 건수와 PostgreSQL의 `RAW_EVENT` 적재 건수를 대조하는 검증 쿼리 작성.
- [ ] 주 1회(또는 1일 1회) 유실률(Loss Rate)을 검사하여 엔지니어링 Slack 채널로 리포트를 발송하는 Cron Job(또는 GitHub Actions Schedule) 설정.
- [ ] PostgreSQL의 `pg_stat_activity`를 조회하여 교착상태(Deadlock)나 Long-Running Query를 탐지하는 쿼리 작성.
- [ ] 5분 주기로 Deadlock을 검사하고, 발견 시 즉각 Alert 시스템(Slack/PagerDuty)으로 알림을 보내는 크론 스크립트 배포.

## ✅ Acceptance Criteria (BDD)
- **Given**: 시스템이 운영 중인 상태에서
- **When**: 5분 주기 크론 스크립트가 실행될 때 DB 내에 교착상태(Deadlock)가 탐지되면
- **Then**: 발생 즉시 관련 로그와 함께 경고 알림이 발송되어야 한다. (Deadlock 발생률 목표 = 0%)
- **When**: 유실 대조 스크립트가 실행되면
- **Then**: 큐 적재 건수와 DB 레코드 건수 간 불일치(0% 미달)가 확인될 경우, 즉시 데이터 정합성 에러 알림이 발송되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 스크립트 쿼리는 인덱스를 타도록 최적화되어, 메인 DB 트랜잭션 처리에 락(Lock) 지연을 유발하지 않아야 한다.
