---
name: Feature Task
title: "[Feature] AIE-002b: 문맥 충돌(Context Collision) 감지 및 Diff 생성 로직"
labels: 'feature, priority:high, ai-engine'
---

## 🎯 Summary
- 기능명: [AIE-002b] 문맥 충돌(Context Collision) 감지 및 Diff 생성 로직
- 목적: 이기종 채널에서 동일 주제에 대해 상반된 의견이나 충돌되는 팩트가 수집되었을 때, 이를 강제로 덮어쓰지 않고 충돌(Diff) 내역을 보존하여 사용자(실무자)의 최종 결정을 돕는다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.2 (REQ-FUNC-008)

## 📝 Task Breakdown
- [ ] 병합 로직(AIE-002a) 과정에서 발화자(author) 간, 또는 채널 간 논리적 모순이 있는 팩트를 식별하도록 프롬프트 지시어 보강.
- [ ] 모순이 감지될 경우, 두 의견을 각각 `Option A (발화자/시간)`, `Option B (발화자/시간)` 형식의 Diff 구조로 포맷팅하는 모듈 작성.
- [ ] 생성된 초안 텍스트 내에 충돌 구간임을 명시하는 시각적 마커(예: `[CONFLICT_DETECTED]`) 삽입.
- [ ] 프론트엔드 에디터에서 해당 충돌 마커를 인식하여 UI를 분리 렌더링할 수 있도록 JSON 메타데이터(conflict_zones) 반환 포맷 구성.
- [ ] LLM 추론 실패(Timeout/OOM) 시 초안 생성을 보류하고 `fusion_degraded` 상태 이벤트를 발생시켜 사용자 대시보드에 알림을 표시하는 Graceful Degradation 처리. (C-TEC-006 준수)

## ✅ Acceptance Criteria (BDD)
- **Given**: Slack에서는 "출시일 15일 연기"라고 논의되고, Jira에서는 "출시일 변경 없음"이라고 기재된 상충 데이터가 입력되었을 때
- **When**: 병합 및 충돌 감지 모듈이 동작하면
- **Then**: 어느 한쪽의 의견을 무시하지 않고 두 팩트를 대조하는 Diff 블록 구조화 데이터가 초안에 포함되어야 한다.
- **Then**: 충돌 블록에는 양측의 원본 발화 채널, 발화자, 타임스탬프 메타데이터가 명확히 명시되어야 한다.
- **Given**: LLM 추론 서버가 Timeout 또는 OOM으로 응답 불가 상태일 때
- **When**: 병합 엔진이 추론 요청에 실패하면
- **Then**: 초안 생성이 보류(pending_retry)되고, 60초 이내에 사용자 대시보드에 "AI 엔진 일시 중단" 경고가 표시되어야 한다. Webhook 수신은 중단 없이 계속되어야 한다. (C-TEC-006)

## 🛡️ Constraints (NFRs)
- 성능 제약: 충돌 감지를 위해 너무 복잡한 프롬프트 연쇄(Chain)를 발생시킬 경우 지연 시간이 길어질 수 있으므로, 단일 LLM 추론 사이클 내에서 해결할 수 있도록 프롬프트를 최적화해야 한다.
