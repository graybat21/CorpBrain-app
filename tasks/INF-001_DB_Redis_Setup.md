---
name: Feature Task
title: "[Feature] INF-001: PostgreSQL DB 및 Redis Queue 인프라 구축"
labels: 'feature, priority:high, infrastructure'
---

## 🎯 Summary
- 기능명: [INF-001] PostgreSQL DB 및 Redis Queue 인프라 구축
- 목적: CorpBrain의 원시 데이터(RAW_EVENT)와 초안(SEMANTIC_DRAFT)을 영구 저장할 Primary DB와, 이벤트 수신 시 오버헤드를 줄이고 비동기 파이프라인 처리를 담당할 경량 메시지 큐(Redis) 환경을 프로비저닝한다.

## 🔗 References (Spec & Context)
- SRS 문서: §1.5.1 (C-TEC-001, C-TEC-002)

## 📝 Task Breakdown
- [ ] AWS RDS(또는 독립 서버) 기반 PostgreSQL 15 이상 버전 클러스터 프로비저닝 및 접속 환경 구성.
- [ ] AWS ElastiCache(또는 독립 서버) 기반 Redis 환경 프로비저닝 및 접속 환경 구성.
- [ ] DB 및 Redis 접근 제어(VPC 설정, Security Group, 방화벽) 정책 수립 및 적용.
- [ ] 개발/스테이징/프로덕션 환경별 접속 정보(URI, Secrets)를 환경변수(Env/Secrets Manager)에 등록.
- [ ] (선택) 로컬 개발 환경용 `docker-compose.yml` (PostgreSQL + Redis) 스크립트 작성 및 배포.

## ✅ Acceptance Criteria (BDD)
- **Given**: 백엔드 개발자가 로컬 또는 배포 환경에서 시스템을 구동할 때
- **When**: 지정된 DB URL 및 Redis URL로 연결을 시도하면
- **Then**: 정상적으로 Connection이 수립되고, 읽기/쓰기(Pub/Sub) 동작이 오류 없이 수행되어야 한다.

## 🛡️ Constraints (NFRs)
- 보안 제약: DB 및 Redis 포트는 외부 인터넷에 직접 노출되지 않아야 하며, VPC 내부 통신을 원칙으로 한다.
- 아키텍처 제약: 데이터 유실 방지를 위해 Redis는 최소한의 Persistence(AOF/RDB) 설정이 고려되어야 한다 (C-TEC-001).
