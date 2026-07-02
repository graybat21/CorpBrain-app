---
name: Feature Task
title: "[Feature] SSOT-001: API Contract/DTO 스키마 정의 (OpenAPI Spec)"
labels: 'feature, priority:high'
---

## 🎯 Summary
- 기능명: [SSOT-001] API Contract/DTO 스키마 정의 (OpenAPI Spec)
- 목적: 전체 기능 개발의 기준점(SSOT)이 되는 REST API Endpoint의 입출력 규격 및 DTO 모델을 OpenAPI 스펙으로 정의하여 프론트엔드와 백엔드의 병렬 개발을 지원한다.

## 🔗 References (Spec & Context)
- SRS 문서: §6.1 API Endpoint List, §3.3.1 Internal Core API

## 📝 Task Breakdown
- [ ] Next.js (App Router) 환경의 Route Handlers에 맞춰 `api/v1` 구조의 설계 문서 작성.
- [ ] `/webhook/slack` 및 `/webhook/jira` 인바운드 수신용 Endpoint 스키마 정의 (Request Payload 형식 검증 로직 포함).
- [ ] `POST /api/v1/drafts/generate` Endpoint의 Request DTO(`workspace_id`, `time_range`, `channels`, `masking_enabled`) 및 Response DTO 스키마 명세 작성.
- [ ] `PATCH /api/v1/drafts/{draft_id}/review` Endpoint의 Request DTO(`action`, `edits`, `publish_to`) 및 Response DTO 스키마 명세 작성.
- [ ] `POST /api/v1/masking-rules` 및 조회 API(`GET /api/v1/drafts/{id}`, `GET /api/v1/reports/roi`, `GET /api/v1/health`)의 입출력 DTO 명세 작성.
- [ ] OpenAPI 3.0(또는 3.1) 포맷의 YAML/JSON 파일 생성 (또는 Swagger UI 연동 설정 파일 작성).

## ✅ Acceptance Criteria (BDD)
- **Given**: 프론트엔드 개발자가 API 문서를 참조하려는 상황에서
- **When**: OpenAPI 스펙 파일(또는 Swagger/Redoc UI)을 열람하면
- **Then**: 총 8개의 코어 API Endpoint에 대한 Request/Response 스키마, 데이터 타입, 필수 여부, 그리고 에러 응답 포맷(400, 401, 403, 429 등)이 명확히 정의되어 있어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: 각 API 경로에 필요한 인증 헤더(Bearer Token) 및 필요 권한이 명시되어야 한다.
- 아키텍처 제약: P1(데이터·계약 우선) 원칙에 따라 이 스키마가 승인되기 전에는 백엔드 비즈니스 로직(AIE, API Core) 구현을 시작할 수 없다.
