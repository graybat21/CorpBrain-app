---
name: Feature Task
title: "[Feature] API-M002: 초안 생성 완료 Push 알림 백엔드 (SSE/WebSocket)"
labels: 'feature, priority:medium, api-middleware'
---

## 🎯 Summary
- 기능명: [API-M002] 초안 생성 완료 Push 알림 백엔드
- 목적: 초안 생성(LLM 추론) 작업이 최대 15초가량 소요될 수 있으므로, 비동기 작업 완료 시 클라이언트(대시보드)에 실시간으로 완료 알림을 푸시하여 UX를 개선한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.4.1 핵심 시퀀스 다이어그램 ("DG→UI: 초안 생성 완료 알림")

## 📝 Task Breakdown
- [ ] 서버-클라이언트 간 실시간 단방향 통신을 위한 Server-Sent Events (SSE) 엔드포인트 또는 WebSocket 서버 채널 구성.
- [ ] 클라이언트가 접속 시 `workspace_id` 또는 `user_id`를 기반으로 고유한 연결 세션 유지.
- [ ] API-W001(초안 생성) 비동기 파이프라인의 가장 마지막 단계(DB `SEMANTIC_DRAFT` 적재 직후)에 Pub/Sub 이벤트를 발행하는 로직 추가.
- [ ] 알림 데몬(또는 SSE 라우트)이 해당 이벤트를 수신하여 특정 클라이언트에게 `draft_generated` 메시지와 `draft_id` 페이로드를 푸시.

## ✅ Acceptance Criteria (BDD)
- **Given**: 실무자가 대시보드 화면을 열어둔 상태에서 백그라운드로 초안 생성이 진행 중일 때
- **When**: LLM 파이프라인 처리가 완료되고 DB에 저장이 끝나는 즉시
- **Then**: 클라이언트 측에 SSE(또는 WS) 메시지가 푸시되어, 화면 새로고침 없이 "새로운 초안이 생성되었습니다" 라는 알림(Toast)이 발생해야 한다.

## 🛡️ Constraints (NFRs)
- 확장성 제약: 다중 워커/인스턴스 환경에서 SSE 연결을 유지하기 위해, 특정 노드에 종속되지 않도록 Redis Pub/Sub을 중간 브로커로 사용하여 이벤트를 중계해야 한다.
