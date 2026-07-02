---
name: Feature Task
title: "[Feature] APP-005: ROI 대시보드 리포트 화면 UI"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-005] ROI 대시보드 리포트 화면 UI
- 목적: 서비스 도입의 핵심 지표인 '절감된 업무 시간'과 '인건비 절감액(ROI)'을 시각적인 차트와 KPI 카드로 렌더링하여 B2B 세일즈 소구점을 극대화한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.6 REQ-FUNC-024
- 선행 태스크: DES-004 (ROI 리포트 UI/UX 설계), API-R004 (ROI 리포트 조회 Query)

## 📝 Task Breakdown
- [ ] `/reports/roi` 페이지 라우팅 구성 및 DES-004 디자인 시안 적용.
- [ ] API-R004(ROI 리포트 조회) 엔드포인트를 Server Component에서 호출하여 집계 데이터 확보.
- [ ] Recharts(또는 Tremor) 라이브러리를 활용한 주간/월간 절감 시간 트렌드 Bar/Line 차트 컴포넌트 구현 (next/dynamic 지연 로딩 적용).
- [ ] Summary KPI 카드 UI 구현: 총 누적 절감 시간, 누적 절감액(KRW), 시스템 승인률 Big Number 표시.
- [ ] 데이터 미존재 시(온보딩 직후 0건) Empty State 안내 UI: "아직 데이터가 충분하지 않습니다. 첫 번째 초안을 승인하면 성과 지표가 집계됩니다."

## ✅ Acceptance Criteria (BDD)
- **Given**: Manager 권한 사용자가 ROI 리포트 페이지에 접속했을 때
- **When**: 화면이 로드되면
- **Then**: API-R004에서 받아온 데이터가 직관적인 차트와 숫자로 렌더링되어 "이번 달 총 15시간 절감, 50만원 비용 효과" 등의 문구가 표시되어야 한다.
- **Given**: 승인된 초안이 0건인 워크스페이스에서
- **When**: 사용자가 ROI 대시보드에 최초 접근하면
- **Then**: 빈 차트 대신 Empty State 안내 UI가 표시되어야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 차트 라이브러리가 초기 로딩 번들 사이즈에 영향을 주지 않도록, `next/dynamic` 등을 활용한 Code Splitting을 적용해야 한다.
