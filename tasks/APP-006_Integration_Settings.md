---
name: Feature Task
title: "[Feature] APP-006: 시스템 연동(Slack/Jira/Notion) 설정 관리 화면 UI"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-006] 시스템 연동(Slack/Jira/Notion) 설정 관리 화면 UI
- 목적: 워크스페이스 관리자가 CorpBrain과 연동할 외부 서비스(Slack, Jira, Notion, Confluence)의 OAuth 연결 상태를 확인하고, 채널/프로젝트 매핑을 관리할 수 있는 설정 화면을 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: §3.2 (External System Interface)
- 선행 태스크: None

## 📝 Task Breakdown
- [ ] `/settings/integrations` 페이지 라우팅 및 레이아웃 구성.
- [ ] 연동 서비스별(Slack, Jira, Notion, Confluence) 카드 컴포넌트: 연결 상태(Connected/Disconnected), 마지막 동기화 시간 표시.
- [ ] '연결하기' 버튼 클릭 시 각 서비스의 OAuth 인증 플로우(redirect) 트리거 로직 구현.
- [ ] 연결된 서비스의 채널/프로젝트 선택 UI: 모니터링 대상 Slack 채널 또는 Jira 프로젝트를 다중 선택하여 저장.
- [ ] '연결 해제' 버튼 및 확인 다이얼로그(Destructive Action 경고) 구현.

## ✅ Acceptance Criteria (BDD)
- **Given**: Admin 사용자가 연동 설정 페이지에 접속했을 때
- **When**: Slack 카드의 '연결하기' 버튼을 클릭하면
- **Then**: Slack OAuth 인증 페이지로 리다이렉트되고, 인증 완료 후 상태가 'Connected'로 변경되어야 한다.
- **When**: 연결된 Slack 서비스의 '연결 해제' 버튼을 클릭하면
- **Then**: "연결을 해제하면 데이터 수집이 중단됩니다" 경고 다이얼로그가 표시되고, 확인 시에만 해제되어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: OAuth Token은 클라이언트에 노출되지 않으며, Server Action을 통해서만 토큰 교환이 이루어져야 한다 (SEC-004 AES-256 암호화 모듈 참조).
