---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-CMD-03: Option B 선택 시 Ollama 데몬 무인 설치 및 백그라운드 모델 Pull"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-CMD-03] Ollama 무인 설치
- 목적: 완전 오프라인 환경을 위해 사용자가 Option B를 선택하고 데몬이 없을 경우, OS 명령어 레벨에서 백그라운드로 Ollama 설치 및 지정된 경량 모델 풀링(Pull)을 실행한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-010`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 현재 OS(Windows) 타겟 환경에 맞는 설치 여부 확인(명령어 경로 조회)
- [ ] 미설치 시 Installer 다운로드 및 무인(Silent) 실행 스크립트 트리거 로직 구현
- [ ] 설치 후 `ollama pull [model_name]` Subprocess 실행 및 표준 출력(stdout) 파싱
- [ ] 프론트엔드 진행 상황(Progress) 전달용 웹소켓 혹은 Polling 상태 저장

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: Ollama 미설치 환경에서 자동 설치 트리거
- Given: Ollama가 설치되지 않은 Windows 환경
- When: Option B 설정을 저장하고 설치 명령을 백그라운드로 호출함
- Then: 설치 프로세스가 백그라운드에서 실행되며, 진행 상태가 API(상태 조회)를 통해 지속 갱신된다.

## :construction: Dependencies & Blockers
- Depends on: API-003
- Blocks: LLM-FE-02
