---
name: Feature Task
title: "[Feature] EXT-002: Confluence API 위키 발행 연동"
labels: 'feature, priority:medium, external-system'
---

## 🎯 Summary
- 기능명: [EXT-002] Confluence API 위키 발행 연동
- 목적: 기업 표준 위키인 Confluence를 사용하는 고객사를 위해, 승인된 문서 초안을 Confluence Space 하위 페이지로 자동 퍼블리싱하는 어댑터를 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.1 External Systems, §4.1.5 (REQ-FUNC-021)

## 📝 Task Breakdown
- [ ] Atlassian OAuth 2.0 (3LO) 연동 플로우 구현 및 인증 토큰 획득/저장(암호화) 모듈.
- [ ] 시스템의 내부 Markdown 문서를 Confluence Storage Format (XHTML 기반)으로 변환하는 Serializer 모듈 구현.
- [ ] Atlassian Cloud REST API `POST /wiki/rest/api/content` 호출 로직 구현.
- [ ] 페이지 생성 시 부모 페이지(Ancestor) 지정 및 딥링크 앵커 보존 규칙 적용.

## ✅ Acceptance Criteria (BDD)
- **Given**: 사용자가 연동 설정에서 Confluence Space를 타겟으로 연결해 둔 상태에서
- **When**: 문서 초안을 검토 후 "승인 및 발행(Confluence)" 액션을 수행하면
- **Then**: Confluence API를 통해 새 페이지가 정상적으로 생성되고 해당 URL이 반환되어야 한다.
- **Then**: 본문 내의 하이퍼링크(Trust-Anchor)가 올바르게 렌더링되어 클릭 시 원본(Slack/Jira)으로 전환 가능해야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: Confluence API는 간헐적인 지연이 발생할 수 있으므로 발행 요청은 동기식(Sync) UI 블로킹을 피하고 백그라운드 큐 기반으로 처리할 것을 권장한다.
