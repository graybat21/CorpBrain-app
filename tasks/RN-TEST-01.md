---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] RN-TEST-01: Rename Undo 100% 원복 통합 테스트"
labels: 'test, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [RN-TEST-01] Undo 무결성 테스트
- 목적: Batch Rename 실행 후 Undo 기능이 `Rename_History` DB를 기반으로 100% 원본 상태로 복구하는지 통합 테스트로 검증한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.1.4 → **REQ-FUNC-019** (Undo Rename)
- 신뢰성: `04_SRS-Drafts/피벗 버전/SRS-draft_v0.6_OPUS.md` §4.2 → **REQ-NF-009** (Rename Rollback Integrity)
- 검증 TC: TC-REL-003

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 50개 파일 Batch Rename → Undo 시나리오 통합 테스트 작성
- [ ] Undo 중 파일 Lock으로 부분 실패 시 실패 목록 반환 검증
- [ ] Undo 후 물리 경로와 파일 해시값 일치 확인

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 100% Undo 원복
- Given: 50개 파일이 Batch Rename으로 변경됨
- When: Undo 커맨드를 실행함
- Then: 모든 파일의 원본 경로와 이름이 100% 복원된다.

Scenario 2: 부분 실패 시 실패 목록 표시
- Given: Undo 중 2개 파일이 다른 프로세스에 의해 잠김
- When: Undo를 실행함
- Then: 48개는 원복되고 2개 실패 파일 목록이 반환된다.

## :gear: Technical & Non-Functional Constraints
- 신뢰성: REQ-NF-009 — 50개 파일 기준 통합 테스트
- 트랜잭션: `Rename_History` 역순 조회 후 OS rename

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-REL-003 자동화 테스트 통과
- [ ] RN-CMD-03 DoD 연계 완료

## :construction: Dependencies & Blockers
- Depends on: RN-CMD-02, RN-CMD-03
- Blocks: None
