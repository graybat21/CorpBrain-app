---
name: Feature Task
title: "[Feature] APP-002: 딥링크 앵커 호버(툴팁/팝오버) 및 네비게이션 UI"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-002] 딥링크 앵커 호버(툴팁/팝오버) 및 네비게이션 UI
- 목적: CorpBrain의 핵심 차별점인 Trust-Anchor(딥링크) 기능을 시각적으로 구현하여, 사용자가 요약 문장의 원본 근거를 즉시 확인하고 외부 소스(Slack/Jira)로 이동할 수 있는 인터랙션을 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.3 REQ-FUNC-011, REQ-FUNC-012
- 선행 태스크: DES-001 (Trust-Anchor UI/UX 설계), APP-001 (HITL 에디터 UI)

## 📝 Task Breakdown
- [ ] APP-001 에디터 패널의 본문 렌더링 시, `deeplink_map` 데이터와 매칭되는 텍스트 Span에 시각적 하이라이트(연한 밑줄/배경) 스타일링 적용.
- [ ] 하이라이트 영역 마우스 호버(Hover) 시 팝오버(Popover) 컴포넌트 렌더링: 원본 발화자, 채널명, 타임스탬프, 원문 미리보기 표시.
- [ ] 팝오버 내 '원본 보기' 클릭 시 우측 패널 스크롤 이동 또는 외부 딥링크(Slack permalink / Jira issue URL) 새 창 열기 액션 수행.
- [ ] 키보드 접근성: Tab 키로 Trust-Anchor 간 이동, Enter 키로 팝오버 열기 지원.
- [ ] `deeplink_map`이 비어 있는 문장에는 하이라이트를 적용하지 않고, 매핑 누락 문장에는 경고 아이콘(⚠️) 표시.

## ✅ Acceptance Criteria (BDD)
- **Given**: 실무자가 APP-001 에디터 화면에서 AI 요약 초안을 읽고 있을 때
- **When**: 파란색 밑줄이 적용된 특정 문장(Trust-Anchor) 위에 마우스를 올리면
- **Then**: 팝오버에 해당 요약의 근거가 된 원본 메시지 작성자, 시간, 채널 정보가 300ms 이내에 표시되어야 한다.
- **When**: 팝오버의 '원본 보기' 링크를 클릭하면
- **Then**: Slack 원본 메시지 permalink 또는 Jira 이슈 페이지가 새 탭에서 열려야 한다.

## 🛡️ Constraints (NFRs)
- UI/UX 제약: Trust-Anchor 하이라이트는 사용자의 독해를 방해하지 않는 옅은 색상(연한 밑줄)이어야 하며, 호버 시에만 상호작용 피드백을 제공해야 한다.
- 성능 제약: `deeplink_map`에 100개 이상의 매핑이 있어도 초기 렌더링 성능이 저하되지 않도록 가상화(Virtualization) 또는 지연 하이라이팅을 적용해야 한다.
