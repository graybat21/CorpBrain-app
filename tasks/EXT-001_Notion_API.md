---
name: Feature Task
title: "[Feature] EXT-001: Notion API 위키 발행 연동"
labels: 'feature, priority:high, external-system'
---

## 🎯 Summary
- 기능명: [EXT-001] Notion API 위키 발행 연동
- 목적: 실무자가 대시보드에서 승인한 최종 초안을 사내 Notion 워크스페이스의 특정 데이터베이스나 페이지에 자동으로 발행(Publish)하는 어댑터 모듈을 구현한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.1 External Systems, §4.1.5 (REQ-FUNC-021)

## 📝 Task Breakdown
- [ ] Notion OAuth 2.0 연동 프로세스 구현 및 획득한 Access Token을 DB(`INTEGRATION`)에 암호화(SEC-004) 보관하는 설정.
- [ ] 내부 포맷(Markdown/Plain Text)을 Notion API의 `Block Object` 기반 JSON 트리 구조로 변환하는 파서(Serializer) 작성.
- [ ] 딥링크(deeplink_map) 정보를 Notion의 Text Link 객체로 올바르게 주입하는 로직 구현.
- [ ] API-W003(승인/반려 Command) 호출 시, 백그라운드에서 `POST https://api.notion.com/v1/pages` API를 호출하여 문서를 발행하는 서비스 모듈 구현.

## ✅ Acceptance Criteria (BDD)
- **Given**: 사용자가 대시보드 연동 설정에서 Notion을 연결해 둔 상태에서
- **When**: 딥링크가 포함된 초안을 열람 후 "승인 및 발행(Notion)" 버튼을 클릭하면
- **Then**: 3초 이내에 사내 Notion의 지정된 경로에 새 페이지가 생성되어야 한다.
- **Then**: 생성된 페이지 본문에는 기존 포맷팅과 원본 딥링크 하이퍼링크가 완벽히 보존된 상태여야 하며, 생성된 페이지의 URL이 반환되어야 한다.

## 🛡️ Constraints (NFRs)
- 의존성 제약: 이 모듈은 API-W003 실행 완료 단계의 필수 서브루틴으로 동작해야 하며, 발행 실패 시 큐를 통한 비동기 재시도 로직이 확보되어야 한다.
