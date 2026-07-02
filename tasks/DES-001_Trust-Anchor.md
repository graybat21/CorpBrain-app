---
name: Feature Task
title: "[Feature] DES-001: Trust-Anchor (딥링크) UI/UX 설계"
labels: 'feature, priority:high, design'
---

## 🎯 Summary
- 기능명: [DES-001] Trust-Anchor (딥링크) UI/UX 설계
- 목적: AI가 생성한 초안 문장에 원본 출처를 100% 매핑하여 팩트체크를 지원하는 핵심 가치(Trust-Anchor)를 직관적으로 전달하기 위한 UI/UX를 설계한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.3 F3 (REQ-FUNC-010 ~ 013)

## 📝 Task Breakdown
- [ ] 초안 본문 내 요약 문장에 딥링크 앵커(하이퍼링크 또는 아이콘)를 시각적으로 표시하는 디자인 시안 작성.
- [ ] 문장 마우스 오버(Hover) 시 1초 이내에 렌더링될 툴팁 또는 팝오버 컴포넌트(원본 채널명, 작성자, 타임스탬프 정보 포함) UI 설계.
- [ ] 클릭 시 새 창 전환 효과 및 로딩 인디케이터 등 마이크로 인터랙션 정의.
- [ ] 원본 메시지가 삭제되거나 아카이브된 경우 표시될 ⚠️ 경고 배지 및 '원본 삭제됨' 안내 토스트 알림 UI 설계.

## ✅ Acceptance Criteria (BDD)
- **Given**: 디자이너 및 프론트엔드 개발자가 Trust-Anchor 컴포넌트를 구현하려는 상태에서
- **When**: DES-001의 Figma 시안(또는 디자인 가이드라인)을 확인하면
- **Then**: 마우스 오버 시의 툴팁, 정상 클릭 동작, 삭제된 원본 클릭 시의 에러 토스트(경고 배지) 등 3가지 주요 상태(Normal, Hover, Error)에 대한 UI 명세와 마이크로 애니메이션 지침이 명확히 정의되어 있어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 마우스 오버 시 툴팁 렌더링은 지연을 느끼지 못하도록 가벼운 DOM 구조를 전제로 디자인해야 한다 (LCP < 1초 목표).
- 설계 제약: 프론트엔드 모듈 개발(APP-002, APP-003) 전 반드시 선행 완료되어야 한다.
