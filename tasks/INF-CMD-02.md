---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] INF-CMD-02: 로그 파일 로테이션 (50MB/30일) 및 Config 포팅 (JSON)"
labels: 'feature, backend, priority:low, infrastructure'
assignees: ''
---

## :dart: Summary
- 기능명: [INF-CMD-02] 인프라 유틸리티
- 목적: 운영 단계에서 로그 파일이 디스크를 꽉 채우는 것을 방지하기 위해 로테이션 정책을 적용하고, 설정 파일(JSON)을 외부로 분리한다.

## :link: References (Spec & Context)
> :bulb: AI Agent & Dev Note: 작업 시작 전 아래 문서를 반드시 먼저 Read/Evaluate 할 것.
- SRS 문서: `docs/SRS_v1.1_after_grill_OPUS.md` §4.2 → **REQ-NF-014, 015** (Log Rotation, Config Portability)
- 검증 TC: TC-MAINT-001, TC-MAINT-002

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 로깅 라이브러리(Winston, Python `logging` 등) 설정에 50MB 제한 및 30일 보관 옵션 부여
- [ ] 하드코딩된 환경 변수들을 `config.json` 이나 `.env`로 포팅
- [ ] 앱 실행 시 Config 파일 누락 검증 부트스트랩 작성

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 로그 로테이션 발동
- Given: 로그 파일 크기가 50MB에 도달함
- When: 새로운 로그가 기록됨
- Then: 기존 로그 파일이 압축 백업(또는 이름 변경)되고, 새로운 빈 로그 파일에 기록이 이어진다.

Scenario 2: Config Export/Import
- Given: LLM 모드 Option B, Watcher 모드 '실시간'으로 설정됨
- When: 설정을 JSON으로 Export 후 Import함
- Then: 모든 설정값이 동일하게 복원된다 (REQ-NF-015).

## :gear: Technical & Non-Functional Constraints
- 유지보수: 로그 50MB 또는 30일 로테이션 (REQ-NF-014)
- 보안: Config 파일에 API 키 포함 시 암호화 저장

## :checkered_flag: Definition of Done (DoD)
- [ ] TC-MAINT-001, TC-MAINT-002 통과
- [ ] `%LocalAppData%\CorpBrain` 경로 격리 확인 (REQ-NF-004)

## :construction: Dependencies & Blockers
- Depends on: None
