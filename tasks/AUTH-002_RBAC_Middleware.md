---
name: Feature Task
title: "[Feature] AUTH-002: RBAC(Role-Based Access Control) 미들웨어"
labels: 'feature, priority:medium, security'
---

## 🎯 Summary
- 기능명: [AUTH-002] RBAC(Role-Based Access Control) 미들웨어 구현
- 목적: 인증된 사용자라도 직책(Role)에 따라 접근 가능한 기능(예: 관리자 규칙 등록, 팀장급 ROI 조회 등)을 제한하기 위해 역할 기반 접근 제어 시스템을 도입한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.6 (REQ-FUNC-025), §6.1 API Endpoint List (Admin, Manager 권한)

## 📝 Task Breakdown
- [ ] 시스템 역할을 3단계(Admin, Manager, User) 또는 열거형(Enum)으로 정의하는 타입 설정.
- [ ] 컨트롤러 또는 라우터 단에서 특정 Role의 접근만 허용하는 `@Roles('admin')` 데코레이터 또는 권한 검사 미들웨어 팩토리 구현.
- [ ] `POST /api/v1/masking-rules` 엔드포인트에 Admin 권한 제약 적용.
- [ ] `GET /api/v1/reports/roi` 엔드포인트에 Manager 이상 권한 제약 적용.
- [ ] 권한이 부족한 사용자가 접근을 시도할 경우 `403 Forbidden` 상태 코드를 반환하는 예외 처리 작성.

## ✅ Acceptance Criteria (BDD)
- **Given**: 권한이 'User(일반 실무자)'인 클라이언트가
- **When**: 관리자 전용 기능인 커스텀 마스킹 규칙 등록 API(`POST /api/v1/masking-rules`)를 호출하면
- **Then**: `403 Forbidden` 에러가 반환되어 접근이 차단되어야 한다.
- **When**: 'Manager(팀장)' 권한을 가진 사용자가 ROI 리포트 조회 API를 호출하면
- **Then**: 200 OK와 함께 데이터 조회가 정상적으로 수행되어야 한다.

## 🛡️ Constraints (NFRs)
- 구조 제약: AUTH-001 모듈과 긴밀하게 통합되어, JWT 토큰 해석 후 바인딩된 사용자 객체의 Role 필드를 기반으로 판별 로직이 동작해야 한다.
