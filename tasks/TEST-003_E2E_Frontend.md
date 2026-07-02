---
name: Feature Task
title: "[Feature] TEST-003: 프론트엔드 E2E Test (TC-008, 009, 014)"
labels: 'feature, priority:medium, test'
---

## 🎯 Summary
- 기능명: [TEST-003] 프론트엔드 E2E Test (TC-008, 009, 014)
- 목적: SRS §5.4에 정의된 TC-008(에디터 로드), TC-009(Trust-Anchor 클릭), TC-014(초안 승인 플로우)를 Playwright 기반으로 자동화하여, 사용자 관점의 핵심 플로우를 브라우저 레벨에서 검증한다.

## 🔗 References (Spec & Context)
- SRS 문서: §5.4 TC-008, TC-009, TC-014
- 선행 태스크: APP-001 (HITL 에디터 UI), APP-002 (딥링크 호버 UI), APP-003 (배지/토스트 UI)

## 📝 Task Breakdown
- [ ] Playwright 설치 및 E2E 브라우저 테스트 환경(Chromium/Webkit) 구성.
- [ ] E2E용 Seed 데이터 초기화 스크립트: 테스트 계정 1개 + Pending 초안 1건 + Trust-Anchor 매핑 데이터 DB 적재.
- [ ] TC-008 시나리오: 로그인 → 대시보드(APP-009) 진입 → 첫 번째 초안 클릭 → 에디터 화면(APP-001) 정상 로드 확인.
- [ ] TC-009 시나리오: 에디터 화면에서 Trust-Anchor 하이라이트 클릭 → 팝오버(APP-002) 표시 → 원본 정보 확인.
- [ ] TC-014 시나리오: '승인(Publish)' 버튼 클릭 → Success Toast 표시 → 상태가 'Approved'로 변경 확인.

## ✅ Acceptance Criteria (BDD)
- **Given**: 자동화된 Chromium 브라우저가 실행된 상태에서
- **When**: `npx playwright test` 명령어로 E2E 테스트 스위트를 실행하면
- **Then**: TC-008, TC-009, TC-014 시나리오가 UI 에러 없이 모두 Pass하고, 리포트에 Green이 기록되어야 한다.

## 🛡️ Constraints (NFRs)
- 운영 제약: E2E 테스트는 실행 시간이 길므로, 매 `git push`가 아닌 `main` 브랜치 PR 또는 릴리스 버전에 대해서만 CI에서 실행하도록 워크플로우를 분리한다.
