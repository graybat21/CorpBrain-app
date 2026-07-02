---
name: Feature Task
title: "[Feature] TEST-002: AI 엔진 Unit/Integration Test (TC-005~007)"
labels: 'feature, priority:high, test'
---

## 🎯 Summary
- 기능명: [TEST-002] AI 엔진 Unit/Integration Test (TC-005~007)
- 목적: SRS §5.4에 정의된 TC-005~007을 자동화하여, 전처리(AIE-001) → 시맨틱 병합(AIE-002a/b) → Trust-Anchor 매핑(AIE-003) AI 파이프라인 전체의 정확성을 LLM 실제 호출 없이 검증한다.

## 🔗 References (Spec & Context)
- SRS 문서: §5.4 TC-005~007
- 선행 태스크: AIE-002b (Context Collision Diff), AIE-003 (Trust-Anchor Mapping)

## 📝 Task Breakdown
- [ ] TC-005: 더미 Slack/Jira 이벤트 10건을 AIE-001에 입력 → 시간순 정렬 및 정규화 출력 포맷 검증.
- [ ] TC-006: Mocking LLM 어댑터 클래스 구현 — 사전 정의된 '병합 완료 결과물'을 반환하여 실제 LLM 호출(과금)을 회피.
- [ ] TC-007: Mock 기반 병합 결과에 대해 `deeplink_map`이 100% 매핑되었는지, Diff 충돌 마커 포맷이 예상값과 정확히 일치하는지 Assertion.
- [ ] 의존성 주입(DI) 인터페이스로 테스트 환경에서만 LLM Provider를 Mock 클래스로 스위칭할 수 있는 구조 확인.

## ✅ Acceptance Criteria (BDD)
- **Given**: Mocking LLM 모듈이 설정된 테스트 환경에서
- **When**: `npm run test:integration:aie` 명령어로 AI 파이프라인 통합 테스트를 실행하면
- **Then**: 외부 API 호출(과금)이나 타임아웃 지연 없이 5초 이내에 테스트가 종료되어야 한다.
- **Then**: 출력 결과물의 딥링크 매핑 무결성과 Diff 충돌 감지 마커 포맷이 예상값과 일치(Pass)해야 한다.

## 🛡️ Constraints (NFRs)
- 아키텍처 제약: DI 또는 인터페이스 분리 원칙을 준수하여, 테스트 환경에서만 LLM Provider를 Mock 클래스로 안전하게 교체할 수 있는 구조여야 한다.
