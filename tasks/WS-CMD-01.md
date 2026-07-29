---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WS-CMD-01: 2개 이상 로컬 폴더 병합 및 `Workspace_Meta` DB 레코드 삽입"
labels: 'feature, backend, priority:high'
assignees: ''
---

## :dart: Summary
- 기능명: [WS-CMD-01] 로컬 폴더 병합 및 워크스페이스 생성 (Command)
- 목적: 사용자가 OS에서 선택한 한 개 이상의 로컬 폴더 경로를 입력받아 새로운 가상의 워크스페이스로 매핑하고 DB에 영속화한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `REQ-FUNC-001`
- DTO 명세: `API-001`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 여러 폴더 경로를 입력받아 병합(Merge)하는 비즈니스 로직(Service) 구현
- [ ] OS 물리 경로의 존재 여부 및 접근 권한 검증 로직 추가
- [ ] 유효한 경로들을 `Workspace_Meta` DB 테이블에 Insert (트랜잭션 적용)
- [ ] 생성된 워크스페이스의 UUID 반환

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 다중 폴더 병합 생성
- Given: 존재하는 로컬 폴더 경로 A(`C:\docs`)와 B(`D:\assets`)가 주어짐
- When: 병합하여 워크스페이스 생성(Command)을 요청함
- Then: DB에 워크스페이스 메타 레코드가 생성되고, 폴더 A와 B가 하위 경로로 매핑되며 201 Created 응답이 반환된다.

Scenario 2: 유효하지 않은 경로 포함 시 생성 실패
- Given: 존재하지 않는 경로(`Z:\fake_path`)가 포함되어 주어짐
- When: 생성(Command)을 요청함
- Then: 404 Not Found 에러가 발생하며 워크스페이스 생성이 취소된다(DB Rollback).

## :gear: Technical & Non-Functional Constraints
- 성능: 트랜잭션 처리 속도 p95 ≤ 50ms
- 운영체제: Windows 환경의 `MAX_PATH` 제약을 고려한 경로 파싱

## :checkered_flag: Definition of Done (DoD)
- [ ] Acceptance Criteria 충족 및 단위 테스트 (WS-TEST-01) 연계 통과 여부 확인
- [ ] 트랜잭션(Rollback) 엣지 케이스 확인 완료

## :construction: Dependencies & Blockers
- Depends on: DB-001, API-001
- Blocks: WS-QRY-01, SCAN-CMD-01
