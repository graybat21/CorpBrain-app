---
name: Feature Task
title: "[Feature] ING-003: Jira Webhooks 연동 모듈"
labels: 'feature, priority:medium, ingestion'
---

## 🎯 Summary
- 기능명: [ING-003] Jira Webhooks 연동 모듈
- 목적: Jira 프로젝트에서 발생하는 주요 이슈 상태 변경 및 코멘트 추가 이벤트를 실시간 수신하기 위한 전용 핸들러를 구현한다. (Sprint 2 타겟)

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.1 (REQ-FUNC-002)

## 📝 Task Breakdown
- [ ] `/webhook/jira` 전용 엔드포인트 라우팅 구성.
- [ ] `issue_created`, `issue_updated`, `comment_created` 이벤트 페이로드에 대한 타입스크립트 스키마(DTO) 맵핑.
- [ ] 복잡한 Jira JSON 구조에서 필요한 본문(Description/Comment), 작성자, 티켓 링크(URL)만을 추출하여 공통 규격(`NormalizedEventDTO`)으로 변환하는 로직 작성.
- [ ] 내용 변경이 없는 불필요한 업데이트(예: 단순 조회수 증가 등) 이벤트를 필터링하는 로직 적용.

## ✅ Acceptance Criteria (BDD)
- **Given**: Jira 프로젝트 어드민이 CorpBrain Webhook URL을 등록한 상태에서
- **When**: 티켓에 새로운 코멘트가 달리거나 상태(Status)가 변경되면
- **Then**: 해당 이벤트가 `/webhook/jira`로 수신되고, 티켓 원본 딥링크(deeplink_url)가 정상적으로 추출되어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: Jira Cloud의 Webhook은 전역적(Global)일 수 있으므로, 연동된 워크스페이스 ID가 매칭되지 않는 이벤트는 즉시 폐기(Drop)해야 한다.
- 의존성 제약: Slack 연동(ING-002)과 구조적 통일성을 유지하기 위해 동일한 Abstract Webhook Handler 인터페이스를 상속받아 구현할 것을 권장한다.
