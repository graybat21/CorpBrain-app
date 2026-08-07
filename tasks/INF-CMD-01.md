---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] INF-CMD-01: Windows `MAX_PATH` 초과 및 권한 거부 글로벌 예외 처리"
labels: 'feature, backend, priority:high, infrastructure'
assignees: ''
---

## :dart: Summary
- 기능명: [INF-CMD-01] 글로벌 예외 핸들러 구축
- 목적: 파일 스캔 및 읽기 작업 시 빈번히 발생하는 OS 레벨 에러(긴 경로, 권한 거부, 파일 락)가 애플리케이션 전체 크래시(Crash)로 이어지지 않도록 방어하는 안전망을 구축한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.2 → **REQ-NF-007** (Exception Handling)
- 제약: `docs/SRS_v1.1_after_grill_OPUS.md` §1.5.1 → **CON-04** (MAX_PATH)
- 검증 TC: TC-REL-001

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Windows `MAX_PATH` (260자) 우회를 위한 `\\?\` Prefix 자동 붙임 로직 또는 런타임 Manifest 설정 확인
- [ ] 파일 시스템 접근 시 `PermissionError`, `OSError` 등을 포괄하는 글로벌 예외 캐치(Interceptor) 구현
- [ ] 에러 발생 파일은 조용히 Skip 하고 로깅 시스템에 기록(Warning)하는 로직 적용

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 권한 없는 폴더 스캔
- Given: 스캔 대상 폴더 안에 OS에서 접근을 막아둔 관리자 전용 숨김 폴더가 있음
- When: 워크스페이스 스캔을 실행함
- Then: 애플리케이션이 죽지(Crash) 않고, 해당 폴더만 건너뛴 후 나머지 파일 스캔을 정상적으로 완료한다.

Scenario 2: MAX_PATH(260자) 초과 경로 Skip
- Given: 270자 경로를 가진 파일이 스캔 대상에 포함됨
- When: 워크스페이스 스캔을 실행함
- Then: `\\?\` prefix 우회 또는 Skip 처리 후 앱이 정상 동작하고 Warning 로그가 기록된다.

## :gear: Technical & Non-Functional Constraints
- 안정성: 어떠한 파일 시스템 예외도 메인 이벤트 루프를 중단시켜서는 안 됨 (REQ-NF-007)
- 적용 범위: SCAN-CMD-01, RN-CMD-02, DL-CMD-02 등 모든 파일 I/O 모듈

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-REL-001 자동화 테스트 통과
- [ ] SCAN-CMD-01, RN-CMD-02 등 파일 I/O 모듈에 Interceptor 적용

## :construction: Dependencies & Blockers
- Depends on: DB-001
- Blocks: None
