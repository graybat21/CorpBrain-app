---
name: Feature Task
title: "[Feature] APP-008: 초안 생성 완료 실시간 알림(Push Notification) UI"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-008] 초안 생성 완료 실시간 알림(Push Notification) UI
- 목적: AI 엔진이 초안 생성을 완료했을 때, 대시보드에 접속 중인 사용자에게 실시간 알림을 제공하여 즉시 리뷰에 착수할 수 있도록 한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.4.1 "DG→UI: 초안 생성 완료 알림"
- 선행 태스크: API-M002 (Push 알림 백엔드 WebSocket/SSE), APP-001 (HITL 에디터 UI)

## 📝 Task Breakdown
- [ ] API-M002가 제공하는 SSE(Server-Sent Events) 또는 WebSocket 엔드포인트에 대한 클라이언트 구독(Subscribe) 훅(Hook) 구현.
- [ ] 새 초안 생성 완료 이벤트 수신 시 대시보드 우측 상단에 Toast 알림 표시: "새 초안이 생성되었습니다 — [바로 보기]".
- [ ] Toast 내 '바로 보기' 링크 클릭 시 해당 초안 상세 페이지(`/drafts/[id]`)로 클라이언트 사이드 라우팅.
- [ ] 대시보드 초안 목록(APP-009) 자동 갱신(Refetch) 트리거 연동.
- [ ] 네트워크 단절 시 SSE/WebSocket 재연결(Reconnect) 로직 및 연결 상태 인디케이터 표시.

## ✅ Acceptance Criteria (BDD)
- **Given**: 사용자가 대시보드 메인 화면에 접속해 있을 때
- **When**: 백그라운드에서 AI 엔진이 새 초안 생성을 완료하면
- **Then**: 3초 이내에 화면 우측 상단에 "새 초안이 생성되었습니다" Toast 알림이 표시되어야 한다.
- **When**: Toast의 '바로 보기' 링크를 클릭하면
- **Then**: 해당 초안의 상세 에디터 화면(APP-001)으로 즉시 이동해야 한다.

## 🛡️ Constraints (NFRs)
- 안정성 제약: SSE/WebSocket 연결이 끊어진 경우 지수 백오프(Exponential Backoff) 방식으로 자동 재연결을 시도하되, 최대 5회까지만 시도 후 "연결 끊김" 상태 표시로 전환해야 한다.
