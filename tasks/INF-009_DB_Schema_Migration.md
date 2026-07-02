---
name: Feature Task
title: "[Feature] INF-009: DB 스키마 마이그레이션 (5개 엔터티, 인덱스, 제약조건)"
labels: 'feature, priority:high, infrastructure'
---

## 🎯 Summary
- 기능명: [INF-009] DB 스키마 마이그레이션 (5개 엔터티, 인덱스, 제약조건)
- 목적: SSOT 데이터 계약(SSOT-001)에 정의된 데이터 모델을 기반으로 Primary DB인 PostgreSQL에 5개의 핵심 테이블, FK 관계, 검색 최적화 인덱스, 무결성 제약조건을 물리적으로 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §6.2 Entity & Data Model 전체

## 📝 Task Breakdown
- [ ] ORM(Prisma, TypeORM 등) 또는 마이그레이션 툴(Flyway, Alembic) 스크립트 환경 세팅.
- [ ] 5개 핵심 엔터티(`WORKSPACE`, `INTEGRATION`, `RAW_EVENT`, `MASKING_RULE`, `SEMANTIC_DRAFT`)에 대한 DDL (CREATE TABLE) 스크립트 작성.
- [ ] 외래키(FK) 참조 무결성 및 CASCADE/RESTRICT 규칙 설정 (WORKSPACE 삭제 시 하위 데이터 연쇄 삭제 등).
- [ ] 제약조건 추가: `RAW_EVENT`의 `source_deeplink_url` NOT NULL, `SEMANTIC_DRAFT`의 `deeplink_map` JSONB 포맷 제약 등.
- [ ] 검색/조회 최적화용 인덱스 설정 (예: `RAW_EVENT.integration_id`, `SEMANTIC_DRAFT.workspace_id` 단일 및 복합 인덱스).
- [ ] 마이그레이션 실행 및 롤백(Rollback) 스크립트 정상 동작 테스트.

## ✅ Acceptance Criteria (BDD)
- **Given**: 빈 PostgreSQL 데이터베이스가 준비된 상태에서
- **When**: 개발자가 스키마 마이그레이션 명령어(`migrate up`)를 실행하면
- **Then**: 5개의 테이블이 정의된 타입과 제약조건(NOT NULL, ENUM, UUID 등)에 맞게 생성되어야 한다.
- **Then**: 외래키 제약조건 위반 시(예: 존재하지 않는 `workspace_id`로 이벤트 추가) DB 차원에서 트랜잭션 에러(500)가 정상 반환되어 무결성이 지켜져야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 향후 데이터가 방대해질 것을 대비해 `TIMESTAMP` 단위의 파티셔닝(Partitioning) 구조 또는 인덱스(B-tree/GIN)가 사전에 고려되어 설계되어야 한다.
- 의존성 제약: 데이터 수집기(ING)와 백엔드 로직(API/AIE) 개발의 가장 근간이 되므로, 인프라 작업 중 최우선으로 선행 완료되어야 한다.
