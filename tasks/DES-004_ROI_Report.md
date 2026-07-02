---
name: Feature Task
title: "[Feature] DES-004: ROI 리포트 및 관리자 콘솔 UI/UX 설계"
labels: 'feature, priority:medium, design'
---

## 🎯 Summary
- 기능명: [DES-004] ROI 리포트 및 관리자 콘솔 UI/UX 설계
- 목적: B2B 도입 결정권자(팀장 이상)에게 서비스 도입 효과(시간/비용 절감)를 정량적으로 증명하는 ROI 대시보드와, 시스템 연동 관리를 위한 콘솔 화면을 설계한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.6 F6 (REQ-FUNC-024 ~ 025), §3.2 Client Applications

## 📝 Task Breakdown
- [ ] ROI 리포트 화면 내 '월간 절약 시간(분)', '환산 인건비(원)', 'ROI 배수' 등 핵심 KPI 3종을 강조하는 Hero 위젯 카드 설계.
- [ ] 시간 경과에 따른 ROI 추이를 보여주는 데이터 시각화 차트(Line 또는 Bar 형태) 레이아웃 정의.
- [ ] 관리자 콘솔 내 워크스페이스 외부 시스템(Slack, Jira, Notion 등) 연동 상태를 관리하는 Settings 뷰 설계.
- [ ] 일반 실무자가 ROI 메뉴에 접근 시 보여질 권한 없음(403 Forbidden) 에러 안내 화면 디자인.

## ✅ Acceptance Criteria (BDD)
- **Given**: 프론트엔드 개발자가 대시보드의 ROI 화면(APP-005) 및 설정 화면(APP-006)을 구현하려는 상태에서
- **When**: DES-004 디자인 문서를 참조하면
- **Then**: 수치 시각화를 위한 차트 컴포넌트 스펙, 연동 관리 스위치/버튼의 상태 변화(Connected/Disconnected), 권한 분리(RBAC)에 따른 접근 제한 화면 UI가 모두 제공되어야 한다.

## 🛡️ Constraints (NFRs)
- 아키텍처 제약: 데이터 시각화 라이브러리(Recharts, Chart.js 등)로 구현 가능한 보편적인 차트 형태를 지향하여 프론트엔드 복잡도를 통제한다.
- 보안 제약: 권한에 따른 메뉴 노출(팀장급 이상만 ROI 메뉴 활성화)을 반영한 GNB(Global Navigation Bar) 디자인 가이드가 포함되어야 한다.
