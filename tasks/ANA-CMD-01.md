---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-CMD-01: 폴더/파일명 추출 및 고속 분석 중요도 산출 후 DB 업데이트"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-CMD-01] 구조 기반 고속 분석
- 목적: 파일 내용을 열기 전, 폴더 트리 구조와 파일 이름 패턴(정규식 등)만으로 문서의 중요도와 컨텍스트 가중치를 산출하여 DB를 업데이트한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.1.3 → **REQ-FUNC-012** (Fast Analysis)
- API 명세: API-002
- 검증 TC: TC-ANA-001

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 파일 경로 뎁스(Depth) 및 확장자에 따른 기본 가중치 산정 로직 작성
- [ ] 키워드(예: '기획', '설계', '완료') 매칭에 따른 중요도 가점(Bonus) 부여 로직 구현
- [ ] 산출된 중요도 점수(Score)를 `File_Meta` 테이블에 일괄 업데이트

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 이름 기반 중요도 산출
- Given: 스캔이 완료된 `File_Meta` 테이블에 '최종_기획서.docx' 와 '임시_메모.txt' 가 있음
- When: 고속 분석 프로세스가 트리거됨
- Then: '최종_기획서.docx'의 중요도 점수가 '임시_메모.txt'보다 높게 산출되어 DB에 저장된다.

Scenario 2: 0~100 점수 범위 준수
- Given: 다양한 파일명 패턴 10개가 스캔 완료됨
- When: 고속 분석을 실행함
- Then: 모든 파일의 중요도 점수가 0~100 범위 내이며 상위 3개가 UI 하이라이트 대상으로 반환된다.

## :gear: Technical & Non-Functional Constraints
- 성능: 파일명 기반 분석이므로 파일 I/O 없이 p95 < 100ms
- 키워드: '기획', '설계', '최종', '완료' 등 가중치 사전 정의

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-ANA-001 시나리오 통과
- [ ] ANA-FE-01 연동 Mock 데이터 검증

## :construction: Dependencies & Blockers
- Depends on: SCAN-CMD-01
- Blocks: ANA-FE-01
