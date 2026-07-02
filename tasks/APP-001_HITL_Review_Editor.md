---
name: Feature Task
title: "[Feature] APP-001: HITL 초안 리뷰 및 편집 에디터 UI"
labels: 'feature, priority:high, frontend'
---

## 🎯 Summary
- 기능명: [APP-001] HITL 초안 리뷰 및 편집 에디터 UI
- 목적: CorpBrain의 핵심 워크플로우인 Human-in-the-Loop(HITL) 프로세스를 위해, 실무자가 AI 생성 초안을 검토·수정·승인/반려할 수 있는 리치 에디터 화면을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.5 REQ-FUNC-020, REQ-FUNC-023
- 선행 태스크: DES-003 (HITL 대시보드 UI/UX 설계), API-R001 (초안 상세 조회 API)

## 📝 Task Breakdown
- [ ] 초안 상세 화면(`/drafts/[id]`) 라우트 및 레이아웃 구성: 좌측(에디터 패널) / 우측(원본 소스·메타데이터 패널) Split Pane 레이아웃.
- [ ] API-R001을 호출하여 초안 상세 데이터(본문 Markdown, 상태, 타임스탬프, deeplink_map)를 Server Component에서 페칭.
- [ ] Markdown 본문 렌더링 및 인라인 편집(Contenteditable 또는 경량 에디터 라이브러리) 기능 구현.
- [ ] 하단 Action Bar 배치: '승인(Publish)', '수정 요청', '반려' 버튼 및 API-W003 통신 연동.
- [ ] 승인/반려 후 상태 변경 시 Optimistic Update 처리 및 결과 Toast 알림 표시.

## ✅ Acceptance Criteria (BDD)
- **Given**: 실무자가 대시보드에서 'Pending' 상태의 초안을 클릭하여 상세 화면에 진입했을 때
- **When**: AI가 생성한 초안 본문이 로드되면
- **Then**: 좌측 에디터 패널에 Markdown이 렌더링되고, 우측 패널에는 원본 소스 메타데이터(채널, 작성자, 타임스탬프)가 표시되어야 한다.
- **When**: 본문을 수정한 뒤 '승인(Publish)' 버튼을 클릭하면
- **Then**: API-W003 호출이 성공하고, 초안 상태가 'Approved'로 변경되며, 성공 Toast가 표시되어야 한다.

## 🛡️ Constraints (NFRs)
- UI/UX 제약: 에디터 패널의 텍스트 입력 지연(Input Lag)은 50ms 이하로 유지하여 실시간 편집 경험을 보장해야 한다.
- 아키텍처 제약: 에디터 로직은 클라이언트 컴포넌트(Client Component)로 격리하고, 데이터 페칭은 Server Component에서 수행하여 P5(UI/백엔드 분리) 원칙을 준수한다.
