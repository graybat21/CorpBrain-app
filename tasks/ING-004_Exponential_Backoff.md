---
name: Feature Task
title: "[Feature] ING-004: 외부 API Rate Limit 지수 백오프(Exponential Backoff) 구현"
labels: 'feature, priority:high, ingestion'
---

## 🎯 Summary
- 기능명: [ING-004] 외부 API Rate Limit 지수 백오프(Exponential Backoff) 구현
- 목적: 외부 API(Slack, Jira 등) 측의 장애나 Rate Limit(429 Too Many Requests) 응답 시, 데이터를 유실하지 않고 안정적으로 재시도하는 메커니즘을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.1 (REQ-FUNC-004, REQ-FUNC-005)

## 📝 Task Breakdown
- [ ] 외부 통신 유틸리티(Axios/Fetch Wrapper) 단에 `429` 및 `5xx` 에러를 감지하는 인터셉터(Interceptor) 구성.
- [ ] 실패 시 $2^n$ 초(1, 2, 4, 8, 16, 32초) 간격으로 대기하는 Exponential Backoff 알고리즘 구현.
- [ ] 최대 재시도 횟수 제한(Max Retries = 5) 설정.
- [ ] 5회 재시도 실패 시, 에러를 Throw하고 해당 시점까지 확보된 데이터만 파이프라인으로 넘기는 Fallback 로직 구현.
- [ ] Fallback 작동 시 `collection_degraded` 상태 이벤트를 발생시켜 프론트엔드 대시보드 경고 알림(UI 토스트)을 트리거하는 모듈 연결.

## ✅ Acceptance Criteria (BDD)
- **Given**: 시스템이 Slack API에 추가 데이터를 요청하는 과정에서
- **When**: Slack API가 `429 Too Many Requests`를 반환하면
- **Then**: 즉시 실패하지 않고 점진적으로 증가하는 시간 간격으로 최대 5회까지 자동 재시도되어야 한다.
- **When**: 5회 연속 재시도에도 실패하면
- **Then**: 수집 로직이 중단(Degraded)되고 60초 이내에 사용자 대시보드에 데이터 수집 지연 경고가 표시되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 재시도 대기(Wait) 로직이 메인 스레드나 큐 Consumer 워커 전체를 블로킹(Blocking)하지 않도록 비동기 처리되어야 한다.
