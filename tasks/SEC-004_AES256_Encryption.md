---
name: Feature Task
title: "[Feature] SEC-004: 연동 OAuth Token AES-256 암호화 모듈 구현"
labels: 'feature, priority:high, security'
---

## 🎯 Summary
- 기능명: [SEC-004] 연동 OAuth Token AES-256 암호화 모듈 구현
- 목적: 외부 서비스(Slack, Jira 등)와 연동 시 발급받는 OAuth Access Token 등 민감한 인증 정보를 데이터베이스에 평문으로 저장하지 않고, AES-256 규격으로 안전하게 암/복호화하는 모듈을 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.3 (REQ-NF-013), §6.2.2 INTEGRATION 엔터티

## 📝 Task Breakdown
- [ ] 암호화/복호화에 사용할 대칭키(Secret Key) 및 IV(Initialization Vector) 관리 전략 구성 (KMS 연동 또는 환경변수 `ENCRYPTION_KEY` 사용).
- [ ] Node.js의 내장 `crypto` 모듈 등을 활용하여 AES-256-GCM (또는 CBC) 방식의 `encrypt()`, `decrypt()` 유틸리티 함수 작성.
- [ ] ORM(Prisma 등) 연동 시, `INTEGRATION` 테이블의 `oauth_token_encrypted` 필드에 저장하기 직전 자동 암호화 처리되는 Hook(미들웨어) 작성.
- [ ] Webhook 핸들러나 동기화 로직에서 토큰을 사용할 때만 메모리 상에서 복호화(Decrypt)하도록 처리.

## ✅ Acceptance Criteria (BDD)
- **Given**: 고객사가 Slack 연동을 완료하여 OAuth Token을 발급받은 상황에서
- **When**: 해당 토큰이 DB의 `INTEGRATION` 테이블에 저장되면
- **Then**: `oauth_token_encrypted` 컬럼에는 평문 토큰이 아닌 AES-256으로 암호화된 Base64(또는 Hex) 문자열이 저장되어야 한다.
- **When**: 수집기 로직이 외부 API 통신을 위해 토큰을 호출하면
- **Then**: 정상적으로 복호화되어 원래의 평문 토큰 값으로 API 요청이 이루어져야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 암호화에 사용되는 마스터 키는 소스 코드에 하드코딩되어서는 안 되며, 주기적인 키 로테이션(Key Rotation)이 가능한 구조를 지향해야 한다.
