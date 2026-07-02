---
name: Feature Task
title: "[Feature] SSOT-003: Webhook 인바운드 Payload 정규화 스키마 정의 (Slack/Jira)"
labels: 'feature, priority:high'
---

## 🎯 Summary
- 기능명: [SSOT-003] Webhook 인바운드 Payload 정규화 스키마 정의 (Slack/Jira)
- 목적: 서로 다른 형태의 Slack, Jira Webhook Payload를 내부 파이프라인에서 공통으로 처리할 수 있도록 단일화된 내부 정규화 스키마(Adapter DTO)를 정의한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.1 External Systems, §6.1 API Endpoint (#1, #2)

## 📝 Task Breakdown
- [ ] Slack Events API의 `message.channels` Payload 구조 분석 및 타입 정의.
- [ ] Jira Webhooks의 `issue_created`, `issue_updated`, `comment_created` Payload 구조 분석 및 타입 정의.
- [ ] 이기종 플랫폼의 Payload를 공통 형식으로 변환할 `NormalizedEventDTO` 인터페이스 정의 (필수 필드: `integration_id`, `author_id`, `author_name`, `raw_content`, `source_deeplink_url`, `timestamp`, `channel_name`).
- [ ] Slack/Jira 각 플랫폼에서 `source_deeplink_url`을 추출하거나 조립하는 규칙 문서화.
- [ ] 데이터 파서(Parser) 모듈(Adapter 패턴)이 참조할 입출력 규격 명세 작성.

## ✅ Acceptance Criteria (BDD)
- **Given**: Slack과 Jira에서 각각 다른 형태의 JSON Webhook 이벤트가 들어오는 상황에서
- **When**: 해당 페이로드를 정규화 스키마(`NormalizedEventDTO`)에 매핑할 때
- **Then**: 정보의 누락 없이 공통 필드들(`author_name`, `raw_content`, `source_deeplink_url`, `timestamp`)이 완벽히 채워져야 한다.
- **Then**: TypeScript (또는 사용 언어) 환경에서 두 데이터 소스 모두 컴파일 타임 에러 없이 단일 큐 데이터 모델로 변환될 수 있어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: Payload 변환 및 정규화 과정의 지연 시간은 오버헤드가 거의 없어야 한다.
- 아키텍처 제약: 데이터 수집 태스크(ING-001~006) 개발 전 선행되어야 하며, 데이터 유실을 방지하기 위해 Null 허용 여부(Nullable)가 명확히 선언되어야 한다.