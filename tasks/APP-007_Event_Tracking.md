---
name: Feature Task
title: "[Feature] APP-007: GA4 및 Mixpanel 이벤트 트래킹 연동"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-007] GA4 및 Mixpanel 이벤트 트래킹 연동
- 목적: 사용자 행동 데이터(초안 생성 요청, 승인/반려, 페이지 체류 시간 등)를 GA4와 Mixpanel로 수집하여 제품 개선 의사결정에 필요한 정량적 근거를 확보한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.8 REQ-NF-027, REQ-NF-030, REQ-NF-031
- 선행 태스크: None

## 📝 Task Breakdown
- [ ] GA4(Google Analytics 4) 트래킹 ID 설정 및 `@next/third-parties` 또는 GTM(Google Tag Manager) 스크립트 삽입.
- [ ] Mixpanel SDK 초기화 및 환경변수(Project Token) 연동.
- [ ] 핵심 이벤트 정의 및 발화 로직 구현: `draft_generated`, `draft_approved`, `draft_rejected`, `trust_anchor_clicked`, `masking_rule_created`.
- [ ] 사용자 식별(Identify) 호출: 워크스페이스 ID, 유저 역할(Admin/Manager/User)을 Mixpanel User Profile에 연동.
- [ ] 개발/스테이징 환경에서는 이벤트 발화를 비활성화하는 환경 분기 처리.

## ✅ Acceptance Criteria (BDD)
- **Given**: 프로덕션 환경에서 사용자가 초안을 승인했을 때
- **When**: 승인 버튼 클릭 이벤트가 발생하면
- **Then**: GA4 Real-time Report와 Mixpanel Live View에 `draft_approved` 이벤트가 1건 기록되어야 한다.
- **Given**: 개발 환경(`NODE_ENV=development`)에서
- **When**: 동일한 액션을 수행해도
- **Then**: GA4/Mixpanel에 이벤트가 전송되지 않아야 한다.

## 🛡️ Constraints (NFRs)
- 개인정보 제약: 이벤트 페이로드에 문서 본문, PII, 토큰 등 민감 데이터를 절대 포함해서는 안 된다. 이벤트 속성은 ID, 상태값, 타임스탬프 등 비식별 정보로만 구성한다.
