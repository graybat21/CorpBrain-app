---
name: Feature Task
title: "[Feature] EXT-003: Stripe Billing API 연동 (유료 구독 추적)"
labels: 'feature, priority:low, external-system'
---

## 🎯 Summary
- 기능명: [EXT-003] Stripe Billing API 연동 (유료 플랜 구독 추적)
- 목적: 고객사의 Trial 기간 종료, Starter/Team 플랜 전환 등 라이프사이클을 관리하고, 비즈니스 핵심 KPI인 유료 전환율(REQ-NF-029) 추적을 위해 Stripe 결제 시스템을 연동한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.1 External Systems, §4.2.8 (REQ-NF-029)

## 📝 Task Breakdown
- [ ] Stripe Node.js SDK 설치 및 API Key/Webhook Secret 환경변수 등록.
- [ ] `WORKSPACE` 테이블의 `plan_type`, `status` 컬럼과 Stripe Customer ID를 동기화하는 로직 작성.
- [ ] Stripe Webhook (`checkout.session.completed`, `customer.subscription.updated` 등)을 수신할 수 있는 인바운드 핸들러 라우트 생성.
- [ ] 구독 활성화 웹훅 수신 시, DB의 `WORKSPACE.status`를 `active`로 변경하고 유료 전환 이벤트 로깅.

## ✅ Acceptance Criteria (BDD)
- **Given**: Trial 기간 중인 워크스페이스 관리자가 Stripe Checkout 페이지를 통해 결제를 완료했을 때
- **When**: Stripe에서 결제 성공 Webhook 이벤트가 CorpBrain 서버로 전송되면
- **Then**: 해당 Webhook 서명(Signature)이 검증된 후, DB의 워크스페이스 `plan_type`이 업데이트되고 `status`가 `active`로 자동 전환되어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 결제 관련 이벤트는 매우 민감하므로, Stripe Webhook Endpoint에 반드시 Stripe Signing Secret 기반 서명 검증(ING-005와 유사)이 강제되어야 한다.
