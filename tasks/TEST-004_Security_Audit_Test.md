---
name: Feature Task
title: "[Feature] TEST-004: 보안 감사 자동화 Test (TC-019: TLS/AES/OAuth scope)"
labels: 'feature, priority:medium, test'
---

## 🎯 Summary
- 기능명: [TEST-004] 보안 감사 자동화 Test (TC-019)
- 목적: SRS §5.4 TC-019에 정의된 보안 감사 항목(TLS 1.3 적용 여부, AES-256 암호화 무결성, OAuth scope 최소 권한 원칙)을 자동화 테스트로 구현하여, 릴리스 전 보안 컴플라이언스를 기계적으로 보장한다.

## 🔗 References (Spec & Context)
- SRS 문서: §5.4 TC-019
- 선행 태스크: SEC-004 (AES-256 암호화 모듈), INF-008 (TLS 1.3 적용)

## 📝 Task Breakdown
- [ ] TLS 검증 테스트: 스테이징 서버에 대해 `openssl s_client` 또는 프로그래밍 방식으로 TLS 1.3 핸드셰이크 성공 여부 및 하위 버전(TLS 1.1/1.0) 거부 검증.
- [ ] AES-256 암호화 테스트: SEC-004 모듈의 encrypt/decrypt 라운드트립 검증 — 원본과 복호화 결과 일치, 잘못된 키로 복호화 시 실패 확인.
- [ ] OAuth scope 검증 테스트: 각 외부 연동(Slack, Jira, Notion)의 OAuth 토큰이 최소 권한(Minimum Scope)만 요청하는지 설정값 대조 검증.
- [ ] CI 파이프라인에 `npm run test:security` 스크립트 등록 및 Build Break 조건 연동.

## ✅ Acceptance Criteria (BDD)
- **Given**: 스테이징 환경에서 보안 감사 테스트 스위트가 실행될 때
- **When**: `npm run test:security` 명령어를 실행하면
- **Then**: TLS 1.3 핸드셰이크 성공, AES-256 라운드트립 일치, OAuth 최소 scope 준수 — 3개 항목 모두 Pass해야 한다.
- **Then**: 1건이라도 Fail 시 CI 파이프라인이 Build Break 처리되어야 한다.

## 🛡️ Constraints (NFRs)
- 비즈니스 제약: 이 보안 감사 테스트를 통과하지 못한 코드는 어떤 상황에서도 프로덕션 브랜치로 병합될 수 없다 (Hard Constraint).
