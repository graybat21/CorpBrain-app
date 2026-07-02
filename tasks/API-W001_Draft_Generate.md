---
name: Feature Task
title: "[Feature] API-W001: POST /api/v1/drafts/generate (초안 생성 Command)"
labels: 'feature, priority:high, api-core'
---

## 🎯 Summary
- 기능명: [API-W001] POST /api/v1/drafts/generate (초안 생성 Command)
- 목적: 클라이언트의 요청에 따라 수집된 데이터를 조회하고 시맨틱 융합 모듈(AIE)을 호출하여 최종 문서 초안(SEMANTIC_DRAFT)을 데이터베이스에 생성한다. CQRS 패턴의 핵심 Command(Write) 기능을 수행한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.2 (REQ-FUNC-009), §4.2.1 (REQ-NF-002), §6.1 API Endpoint

## 📝 Task Breakdown
- [ ] 라우터 단에서 Request Body(`workspace_id`, `time_range`, `channels`, `masking_enabled`) 유효성 검증(Zod, Class-Validator 등 활용).
- [ ] AUTH-001(JWT 미들웨어)을 연동하여 요청자의 권한 확인 및 `workspace_id` 무결성 검증.
- [ ] AIE-001(전처리) → SEC-001/002(마스킹) → AIE-002(병합) → AIE-003(딥링크 매핑) 파이프라인을 순차적으로 오케스트레이션(Orchestration)하는 서비스 로직 작성.
- [ ] 완료된 최종 초안을 `SEMANTIC_DRAFT` 테이블에 INSERT 하고, 반환값 포맷(`draft_id`, `merged_content`, `deeplink_map` 등) 조립.
- [ ] LLM 서버 지연에 대비한 Timeout 처리 및 에러 로깅 연동.

## ✅ Acceptance Criteria (BDD)
- **Given**: 유효한 JWT 토큰과 파라미터를 지닌 클라이언트가 초안 생성을 요청할 때
- **When**: `POST /api/v1/drafts/generate` 엔드포인트가 호출되면
- **Then**: 모든 AI 및 보안 파이프라인을 거쳐 데이터베이스에 새로운 초안 레코드가 생성되어야 한다.
- **Then**: 클라이언트는 HTTP `201 Created` 응답과 함께 생성된 `draft_id` 및 본문 데이터를 받아야 하며, 이 전체 과정의 p95 지연시간은 15초 이내(REQ-NF-002)여야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 대용량 데이터 처리로 인한 HTTP 타임아웃을 피하기 위해, Vercel AI SDK(또는 기타 프레임워크)의 Streaming 응답이나 비동기 Job 큐(Redis)를 활용한 폴링(Polling) 구조를 적용해야 한다.
- 아키텍처 제약: P2(CQRS) 원칙에 따라 이 엔드포인트는 데이터베이스의 상태를 변경(생성)하는 역할만 집중하며, 단순 조회 로직과 분리된다.
