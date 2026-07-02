---
name: Feature Task
title: "[Feature] SSOT-002: 개발용 Mock 데이터 Seed/Fixture 생성"
labels: 'feature, priority:high'
---

## 🎯 Summary
- 기능명: [SSOT-002] 개발용 Mock 데이터 Seed/Fixture 생성
- 목적: UI 조립(APP) 및 데이터 수집/조회 테스트에 즉시 활용할 수 있도록, 도메인 모델에 부합하는 정교한 Mock 데이터(Seed)를 생성하여 병목을 제거한다.

## 🔗 References (Spec & Context)
- SRS 문서: §6.2 Entity & Data Model

## 📝 Task Breakdown
- [ ] 데이터베이스 스키마(WORKSPACE, INTEGRATION, RAW_EVENT, MASKING_RULE, SEMANTIC_DRAFT) 구조에 맞춘 JSON 기반 Mock Data Fixture 작성.
- [ ] `WORKSPACE` 데이터 생성: 'active', 'suspended', 'trial' 상태별 워크스페이스(plan_type 포함) 3건 이상 생성.
- [ ] `RAW_EVENT` 데이터 생성: Slack, Jira로부터 수집된 가상의 원시 메시지(deeplink_url 포함) 20건 이상 생성.
- [ ] `MASKING_RULE` 데이터 생성: 정규식 타입(pii_regex) 및 커스텀 키워드(custom_keyword) 타입 각각 2건 이상 생성.
- [ ] `SEMANTIC_DRAFT` 데이터 생성: 병합된 초안, `deeplink_map` (100% 매핑), pending/approved 상태의 데이터, edit_history 객체 포함 데이터 생성.
- [ ] 개발 환경용 DB에 해당 Mock 데이터를 자동 주입할 수 있는 Seed 스크립트 작성.

## ✅ Acceptance Criteria (BDD)
- **Given**: 빈 개발용 데이터베이스가 준비된 상태에서
- **When**: 개발자가 `npm run seed` (또는 동등한 Seed 명령어)를 실행하면
- **Then**: WORKSPACE, INTEGRATION, RAW_EVENT, MASKING_RULE, SEMANTIC_DRAFT 테이블에 관계(Foreign Key)가 올바르게 매핑된 Mock 데이터가 즉시 적재되어야 한다.
- **Then**: 프론트엔드에서 목록 조회 및 상세 조회 테스트를 수행할 때 정상적인 뷰가 렌더링될 수 있는 형태의 데이터여야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: Mock 데이터에는 실제 운영 환경의 PII(개인식별정보)나 민감한 회사 정보가 절대 포함되어서는 안 되며, 모두 가상의 더미 데이터(faker 등 활용)로 구성해야 한다.
- 아키텍처 제약: PostgreSQL의 제약 조건(NOT NULL, UNIQUE 등) 및 JSONB 컬럼 포맷에 완벽하게 일치해야 한다.