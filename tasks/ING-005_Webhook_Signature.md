---
name: Feature Task
title: "[Feature] ING-005: Webhook Signature 검증 로직"
labels: 'feature, priority:high, security'
---

## 🎯 Summary
- 기능명: [ING-005] Webhook Signature 검증 로직 (Slack Signing Secret / Jira Secret)
- 목적: 외부에서 인입되는 Webhook 요청이 악의적인 위조 요청(Spoofing)이 아닌, 실제 검증된 연동 플랫폼(Slack/Jira)에서 보낸 정상 트래픽인지 확인하여 보안을 강화한다.

## 🔗 References (Spec & Context)
- SRS 문서: §6.1 API Endpoint, §6.5 Class (validateSignature)

## 📝 Task Breakdown
- [ ] 환경 변수(`SLACK_SIGNING_SECRET`, `JIRA_WEBHOOK_SECRET`) 로드 및 설정 구성.
- [ ] Slack: 헤더의 `x-slack-request-timestamp`와 `x-slack-signature`를 파싱하여 HMAC-SHA256 해시를 생성하고 대조하는 미들웨어/함수 구현.
- [ ] Jira: Webhook 생성 시 발급되는 Secret을 기반으로 HMAC 검증 로직 구현.
- [ ] 타임스탬프 기반 Replay Attack 방어 로직 추가 (요청 시간이 서버 시간 기준 5분 이상 차이 나면 폐기).
- [ ] 검증 실패 시 HTTP 401(Unauthorized) 응답을 즉시 반환하고 감사 로그(Audit Log)를 남기는 처리.

## ✅ Acceptance Criteria (BDD)
- **Given**: 공격자가 임의의 Payload를 구성하여 `/webhook/slack` 엔드포인트를 호출할 때
- **When**: 서명 검증(Signature Validation) 미들웨어가 작동하면
- **Then**: 유효하지 않은 서명으로 판명되어 즉시 `401 Unauthorized`가 반환되고 이벤트 큐에 적재되지 않아야 한다.
- **Given**: 정상적인 Slack 서버가 유효한 헤더와 함께 요청할 때
- **Then**: 서명 검증을 통과하고 `200 OK` 프로세스로 정상 진입해야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: Secret 키는 코드 내 하드코딩 금지. 반드시 KMS나 환경변수로 주입받아야 한다.
- 성능 제약: HMAC 해시 연산은 가벼운 편이나, 수만 건의 동시 요청이 들어올 때 병목이 되지 않도록 컨트롤러 최상단에서 빠르게 Fail-fast 처리해야 한다.
