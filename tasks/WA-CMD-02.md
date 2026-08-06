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
- **확정 사항: `DEC-08`** — 이동/이름변경 이벤트는 `file_id`를 보존한 채 `current_path`만 갱신

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] Python `watchdog` 라이브러리를 사용하여 지정된 워크스페이스 디렉토리 감시 옵저버 세팅
- [ ] Modified 이벤트 발생 시 500ms~1000ms 디바운싱(Debouncing) 적용
- [ ] DB의 `File_Meta.last_modified`(epoch) 값과 OS 물리 파일의 수정 시간을 대조(Check)
- [ ] **`FileMovedEvent` 처리**: `src_path`로 `File_Meta.current_path` 행을 찾아 `current_path`·`file_name`을 `dest_path` 기준으로 UPDATE한다. **새 `file_id`로 재등록하지 않는다** — 재등록하면 위키 딥링크와 누적 통계가 모두 끊긴다 (`DEC-08`)
- [ ] `src_path`에 매칭되는 행이 없으면(감시 외부에서 유입) 신규 파일로 등록
- [ ] 앱 자신의 Rename(RN-CMD-02) 실행 중 발생한 이동 이벤트는 중복 처리하지 않도록 억제(suppress)
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
