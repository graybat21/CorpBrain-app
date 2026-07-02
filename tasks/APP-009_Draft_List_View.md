---
name: Feature Task
title: "[Feature] APP-009: 초안 목록 조회 화면 UI"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-009] 초안 목록 조회 화면 UI
- 목적: 실무자가 자신이 검토하고 승인해야 할 문서 초안들의 목록을 효율적으로 탐색하고 상태별로 분류할 수 있는 대시보드 메인 화면을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: 대시보드 메인 (목록 렌더링 필수)
- 선행 태스크: DES-003 (HITL 대시보드 UI/UX 설계), API-R002 (초안 목록 조회 Query)

## 📝 Task Breakdown
- [ ] Next.js Server Component를 활용하여 API-R002(초안 목록 조회)를 호출하는 대시보드 메인 페이지(`/drafts`) 구현.
- [ ] 리스트 아이템 카드 렌더링: 각 초안의 제목(또는 요약), 타임스탬프, 연동 채널 아이콘(Slack/Jira), 상태 Badge(`Pending`, `Approved`, `Rejected`) 표시.
- [ ] 상단 필터바 컴포넌트: 상태별 탭 필터링(All/Pending/Approved/Rejected) 및 생성일자 범위(Date Picker) 검색 기능.
- [ ] SWR 또는 React Query(또는 Next.js 네이티브 캐싱/재검증)를 적용하여 목록 페이징 및 무한 스크롤(또는 페이지 번호) 처리.
- [ ] APP-008(Push Notification)과 연동: 새 초안 생성 이벤트 수신 시 목록 자동 Refetch.

## ✅ Acceptance Criteria (BDD)
- **Given**: HITL 대시보드 메인 화면에 접속한 사용자가
- **When**: 'Pending(대기 중)' 상태 탭을 클릭하면
- **Then**: 승인 대기 중인 초안 목록만 필터링되어 렌더링되어야 한다.
- **When**: 초안 카드를 클릭하면
- **Then**: 해당 초안의 상세 에디터 화면(APP-001, `/drafts/[id]`)으로 이동해야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 목록 렌더링 시 불필요한 재렌더링을 방지하여 스크롤 프레임 레이트를 60fps로 유지해야 한다.
- 아키텍처 제약: 데이터 페칭은 Server Component에서, 필터/인터랙션은 Client Component에서 분리 처리한다 (P5 원칙).
