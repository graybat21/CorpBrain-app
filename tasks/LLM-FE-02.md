---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-FE-02: Ollama 설치 프로그레스 및 Health Check 상태 아이콘"
labels: 'feature, frontend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-FE-02] LLM 온보딩 및 상태 UI
- 목적: Option B(Ollama) 선택 시 백그라운드 설치 진행률과 LLM 엔진 Health Check 상태를 사용자에게 시각적으로 제공한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.2 → **REQ-FUNC-010, 011** (Local LLM Onboarding, Health Check)
- API 명세: API-003

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Option B 선택 시 Ollama 미설치 감지 후 인라인 프로그레스 바(0~100%) 컴포넌트 렌더링
- [ ] 5초 주기 Health Check 폴링으로 ✅/❌ 상태 아이콘 토글
- [ ] 설치 실패 시 재시도 버튼 및 에러 메시지 표시

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 설치 프로그레스 표시
- Given: Option B 선택 상태이며 Ollama 미설치
- When: 분석을 시도함
- Then: 인라인 프로그레스 바(0~100%)가 표시되고 터미널이 노출되지 않는다.

Scenario 2: Health Check 상태 아이콘
- Given: Option B이며 Ollama 데몬이 정상 구동 중
- When: 5초 주기 Health Check 폴링이 실행됨
- Then: 설정 패널에 ✅ 상태 아이콘이 표시된다.

## :gear: Technical & Non-Functional Constraints
- UX: REQ-FUNC-010 — 백그라운드 설치, 진행률 실시간 갱신
- 가용성: REQ-NF-010 — LLM 미연결 시에도 설정 UI 정상 동작

## :checkered_flag: Definition of Done (DoD)
- [ ] 설치 실패 시 ❌ 아이콘 및 재시도 버튼 제공
- [ ] LLM-CMD-03 Progress API 연동 완료

## :construction: Dependencies & Blockers
- Depends on: API-003, LLM-CMD-01, LLM-CMD-03
- Blocks: None
