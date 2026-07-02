---
name: Feature Task
title: "[Feature] APP-004: 커스텀 마스킹 규칙 등록 및 관리 화면 UI"
labels: 'feature, priority:medium, frontend'
---

## 🎯 Summary
- 기능명: [APP-004] 커스텀 마스킹 규칙 등록 및 관리 화면 UI
- 목적: 워크스페이스 관리자(Admin)가 사내 커스텀 보안·기밀 키워드(MASKING_RULE)를 시각적으로 추가, 수정, 활성화/비활성화할 수 있는 관리 화면을 제공한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.4 REQ-FUNC-018
- 선행 태스크: DES-002 (마스킹 규칙 관리 UI/UX 설계), API-W002 (마스킹 규칙 등록 Command), API-R003 (마스킹 규칙 목록 조회 Query)

## 📝 Task Breakdown
- [ ] 설정 페이지 내 '보안 및 마스킹' 탭 라우팅(`/settings/masking`) 및 레이아웃 구성.
- [ ] API-R003을 호출하여 현재 등록된 마스킹 규칙(키워드/정규식) 목록을 Data Table 형태로 렌더링.
- [ ] '규칙 추가' 모달 다이얼로그 작성: Rule Type(키워드/정규식) 선택, Pattern 입력, 활성 상태 Toggle.
- [ ] 폼 제출 시 API-W002를 호출하고, 성공 시 Toast 알림과 함께 테이블 리스트를 Optimistic Update 처리.
- [ ] Admin 권한이 아닌 사용자가 접근할 경우 '접근 불가' 안내 Fallback UI 표시.

## ✅ Acceptance Criteria (BDD)
- **Given**: Admin 권한 사용자가 보안 설정 탭에 접속했을 때
- **When**: "새 규칙 추가" 버튼을 눌러 모달창에 "프로젝트X"를 입력하고 저장하면
- **Then**: 즉시 로딩 스피너가 표시되고, API 통신 완료 후 테이블 리스트 최상단에 "프로젝트X" 규칙이 활성 상태로 추가되어야 한다.
- **Given**: User(일반) 권한으로 `/settings/masking` URL에 직접 접근했을 때
- **Then**: "관리자 권한이 필요합니다" Fallback UI가 표시되고, 규칙 목록은 노출되지 않아야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 클라이언트 단에서 XSS 공격을 유발할 수 있는 특수문자 입력에 대한 1차 유효성 검사(Client-side Validation)를 적용해야 한다.
- 아키텍처 제약: 마스킹 규칙 CUD(생성/수정/삭제) 로직은 API-W002 서버 액션에 위임하고, 이 컴포넌트는 UI 조립만 담당한다 (P5 원칙).
