---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] WA-CMD-02: `watchdog` 이벤트 감지, 디바운싱 및 타임스탬프 대조 로직"
labels: 'feature, backend, priority:high, daemon'
assignees: ''
---

## :dart: Summary
- 기능명: [WA-CMD-02] 파일 시스템 이벤트 감지
- 목적: OS 단의 파일 변경 이벤트를 감지(Watch)하되, 무의미한 중복 이벤트(단순 속성 변경 등)를 필터링(Debounce)하고 실 내용 변경 시에만 큐에 적재한다.

## :link: References (Spec & Context)
- SRS 문서: `REQ-FUNC-024, 026`

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Python `watchdog` 라이브러리를 사용하여 지정된 워크스페이스 디렉토리 감시 옵저버 세팅
- [ ] Modified 이벤트 발생 시 500ms~1000ms 디바운싱(Debouncing) 적용
- [ ] DB의 `File_Meta.updated_at` 타임스탬프와 OS 물리 파일의 수정 시간을 대조(Check)
- [ ] 내용이 실제로 수정되었을 경우 처리 대기 큐(Queue)에 적재

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 단순 터치 필터링
- Given: 옵저버가 실행 중이고, 파일 속성만 변경되어 OS 이벤트가 발생함
- When: 디바운서 및 필터 검사가 동작함
- Then: 내용 수정 시간이 이전과 동일하므로 이벤트를 버리고(Skip) 큐에 적재하지 않는다.

## :gear: Technical & Non-Functional Constraints
- 안정성: 무한 루프 이벤트 스트림에 의한 데몬 CPU 과점유 방지

## :construction: Dependencies & Blockers
- Depends on: WA-CMD-01
- Blocks: WA-CMD-03, WA-QRY-01
