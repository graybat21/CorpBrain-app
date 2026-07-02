---
name: Feature Task
title: "[Feature] AIE-004: 수정 이력 기반 RL(강화학습) 피드백 루프 데이터 파이프라인"
labels: 'feature, priority:medium, ai-engine'
---

## 🎯 Summary
- 기능명: [AIE-004] 수정 이력 기반 RL(강화학습) 피드백 루프 데이터 파이프라인
- 목적: 실무자가 AI 초안을 검토하며 직접 수정한 내역(edit_history)을 체계적으로 적재하여, 향후 자체 구축 모델(Gemma)의 프롬프트 튜닝이나 RLHF(인간 피드백 기반 강화학습)의 학습 데이터셋으로 활용할 파이프라인을 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.5 (REQ-FUNC-022, 023), §4.2.1 (REQ-NF-005)

## 📝 Task Breakdown
- [ ] 프론트엔드 에디터로부터 인입되는 수정 내역(Original Text, Corrected Text, 문장 Index) JSON 페이로드 처리 컨트롤러 구현.
- [ ] `SEMANTIC_DRAFT` 테이블의 `edit_history` JSONB 컬럼에 해당 내역을 Append하는 비동기 DB 업데이트 쿼리 작성.
- [ ] 단순 텍스트 교정인지, 삭제(Reject)인지, 문맥 충돌 해결인지 수정 유형(Type)을 분류하는 메타데이터 태깅 로직.
- [ ] (추후 고도화 시) 적재된 데이터를 주기적으로 S3 등 콜드 스토리지로 마이그레이션하는 배치 잡(Batch Job) 설계.

## ✅ Acceptance Criteria (BDD)
- **Given**: 사용자가 HITL 대시보드에서 AI가 생성한 초안의 3번째 문장을 수정하고 '승인' 버튼을 클릭했을 때
- **When**: Review API 호출과 함께 해당 파이프라인이 백그라운드에서 동작하면
- **Then**: `edit_history` JSON 객체 내에 수정 전 문장, 수정 후 문장, 타임스탬프가 정확히 구조화되어 DB에 적재되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 사용자의 승인(위키 발행) 속도를 저하시키지 않도록 `edit_history` 적재 트랜잭션은 반드시 비동기로 처리되어야 하며, 적재 지연시간은 ≤ 500ms 이내여야 한다 (REQ-NF-005).
- 보안 제약: 수정 이력 로깅 과정에서도 PII나 마스킹된 기밀 데이터가 복원되어 기록되지 않도록 검열(Sanitization) 정책이 유지되어야 한다.
