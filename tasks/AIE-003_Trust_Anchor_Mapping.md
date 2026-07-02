---
name: Feature Task
title: "[Feature] AIE-003: 요약 문장별 원본 딥링크(Trust-Anchor) 강제 매핑 로직"
labels: 'feature, priority:high, ai-engine'
---

## 🎯 Summary
- 기능명: [AIE-003] 요약 문장별 원본 딥링크(Trust-Anchor) 강제 매핑 로직
- 목적: AI가 생성한 요약 문장이 환각(Hallucination)이 아님을 증명하기 위해, 출력된 각 문장에 원본 메시지의 딥링크(`source_deeplink_url`)를 100% 강제 매핑하는 핵심 알고리즘을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.3 (REQ-FUNC-010), §4.2.2 (REQ-NF-010)

## 📝 Task Breakdown
- [ ] LLM이 병합된 텍스트를 출력할 때, 원본 `event_id` 참조값을 텍스트 스팬(Span) 또는 인덱스에 함께 반환하도록 하는 프롬프트 기법(Citation generation) 적용.
- [ ] 반환된 텍스트를 문장(Sentence) 단위로 토큰화(Tokenize)하는 구문 분석 로직 구현.
- [ ] 추출된 참조값(event_id)을 기반으로 DB에서 `source_deeplink_url`을 역추적(Back-tracking)하여 조인(Join).
- [ ] 문장 인덱스 대비 딥링크 매핑 비율을 검사하는 유효성(Validation) 체크 함수 구현.
- [ ] `deeplink_map` JSON 객체 조립 후 `SEMANTIC_DRAFT` 엔터티 반환 준비.

## ✅ Acceptance Criteria (BDD)
- **Given**: 시맨틱 융합 모듈이 10개의 문장으로 구성된 요약 초안을 생성 완료한 직후
- **When**: Trust-Anchor 매핑 로직 및 검증(Validation)이 실행되면
- **Then**: 10개의 문장 모두(100% 매핑)에 유효한 원본 딥링크 URL이 최소 1개 이상 할당된 `deeplink_map` 객체가 생성되어야 한다.
- **When**: 매핑률이 100% 미만(1문장이라도 누락)일 경우
- **Then**: 시스템은 해당 초안 생성을 즉시 중단(또는 내부 재시도)하고, 에러 로그(Trust-Anchor Failure)를 남겨 환각 위험 문장의 노출을 원천 차단해야 한다.

## 🛡️ Constraints (NFRs)
- 비즈니스 제약: 환각 방어의 가장 강력한 근거가 되는 기능이므로, 딥링크 매핑 무결성(100%)은 시스템의 양보할 수 없는 타협 불가 제약(Hard Constraint)이다 (REQ-NF-010).
