---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] ANA-QRY-01: 1-Depth 폴더별로 분리 가공된 위키 마크다운 구조 반환"
labels: 'feature, backend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [ANA-QRY-01] 생성 위키 조회 (Query)
- 목적: 프론트엔드에서 폴더 탭별로 위키 문서를 렌더링할 수 있도록 1-Depth 디렉토리 단위로 구조화된 마크다운을 묶어 반환한다.

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] `Wiki_Content` 테이블에서 특정 워크스페이스 ID를 기준으로 전체 위키 SELECT
- [ ] 폴더명(키) - 마크다운 본문(값) 형태의 JSON 객체/DTO로 데이터 변환 가공

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 다중 탭 위키 응답
- Given: DB에 '01_FE', '02_BE' 두 개의 위키 문서가 있음
- When: 위키 문서 조회를 요청함
- Then: 배열 또는 맵(Dictionary) 형태로 두 폴더명과 내용이 포함된 JSON 데이터를 반환한다.

## :construction: Dependencies & Blockers
- Depends on: ANA-CMD-03
- Blocks: ANA-FE-02
