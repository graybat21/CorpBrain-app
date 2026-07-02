---
name: Feature Task
title: "[Feature] ING-002: Slack Events API 연동 모듈"
labels: 'feature, priority:high, ingestion'
---

## 🎯 Summary
- 기능명: [ING-002] Slack Events API 연동 모듈
- 목적: Slack 워크스페이스 내 지정된 채널에서 발생하는 메시지 이벤트를 실시간으로 수신하기 위한 전용 핸들러 및 권한 설정 모듈을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.1 (REQ-FUNC-001)

## 📝 Task Breakdown
- [ ] `/webhook/slack` 전용 엔드포인트 라우팅 및 Slack URL Verification 챌린지 핸들링 구현.
- [ ] `message.channels`, `message.groups` 등 타겟 이벤트 타입에 대한 타입스크립트 스키마(DTO) 맵핑.
- [ ] 수신된 Slack Payload를 내부 공통 규격(`NormalizedEventDTO`)으로 1차 변환하는 어댑터 로직 초안 작성.
- [ ] Slack 앱 매니페스트(App Manifest) 파일 작성: `channels:history`, `groups:history` 등 최소한의 읽기 권한(Read-only) Scopes 정의.
- [ ] 봇(Bot) 메시지나 불필요한 시스템 메시지(join/leave 등)를 필터링(Ignore)하는 전처리 로직 적용.

## ✅ Acceptance Criteria (BDD)
- **Given**: Slack 워크스페이스에 CorpBrain 앱이 읽기 전용 권한으로 설치된 상태에서
- **When**: 사용자가 지정 채널에 새 메시지를 게시하면
- **Then**: Slack 서버로부터 `POST /webhook/slack`으로 이벤트가 전송되고, 시스템 메시지나 봇 메시지가 아닌 순수 사용자 발화만 필터링되어 수신되어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 고객사 보안 정책(C-TEC-005) 준수를 위해 메시지 전송(Write) 권한이나 전체 워크스페이스 관리 권한은 절대 요구해서는 안 된다.
- 구조 제약: 수신 직후 상세 파싱은 ING-006(Data Parser)과 분리하여, 이 모듈은 오직 '수신 및 큐 발행'에 집중해야 한다.
