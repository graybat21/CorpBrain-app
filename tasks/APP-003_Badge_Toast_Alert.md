---
name: Feature Task
title: "[Feature] APP-003: 삭제 링크 경고 배지 및 수집 지연 토스트 알림 UI"
labels: 'feature, priority:low, frontend'
---

## 🎯 Summary
- 기능명: [APP-003] 삭제 링크 경고 배지 및 수집 지연 토스트 알림 UI
- 목적: Trust-Anchor의 원본 링크가 삭제·이동되었거나 데이터 수집이 지연될 때, 사용자에게 시각적 경고를 제공하여 초안의 신뢰성 상태를 즉시 파악할 수 있게 한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.3 REQ-FUNC-013 (삭제된 링크 경고), §4.1.1 REQ-FUNC-005 (수집 지연 알림)
- 선행 태스크: APP-002 (딥링크 앵커 호버/네비게이션 UI)

## 📝 Task Breakdown
- [ ] Trust-Anchor의 원본 URL이 404/삭제 상태일 때 해당 하이라이트 영역에 '삭제됨' 경고 배지(Badge) 컴포넌트 오버레이.
- [ ] 경고 배지 클릭 시 "원본 메시지가 삭제되었습니다. 수동으로 근거를 확인하세요." 안내 다이얼로그 표시.
- [ ] 데이터 수집 파이프라인에서 외부 API 지연(Rate Limit 초과 등) 발생 시 대시보드 우측 상단에 토스트(Toast) 알림 표시: "Slack 데이터 수집이 지연되고 있습니다."
- [ ] 토스트 알림은 자동 소멸(5초) + 수동 닫기 지원, 중복 알림 방지(Deduplication) 로직 적용.

## ✅ Acceptance Criteria (BDD)
- **Given**: 에디터 화면에서 Trust-Anchor로 매핑된 원본 Slack 메시지가 삭제된 상태일 때
- **When**: 해당 문장의 Trust-Anchor 하이라이트를 확인하면
- **Then**: 밑줄 옆에 주황색 '⚠️ 삭제됨' 배지가 표시되어야 한다.
- **Given**: 백엔드에서 Slack API Rate Limit 초과로 수집이 지연될 때
- **When**: 사용자가 대시보드에 접속해 있으면
- **Then**: "데이터 수집이 지연되고 있습니다" 토스트 알림이 표시되고, 5초 후 자동으로 사라져야 한다.

## 🛡️ Constraints (NFRs)
- UI/UX 제약: 경고 배지와 토스트는 사용자의 주요 작업 흐름(에디팅, 승인)을 방해하지 않도록 비차단(Non-blocking) 방식으로 표시되어야 한다.
