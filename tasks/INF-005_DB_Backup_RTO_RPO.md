---
name: Feature Task
title: "[Feature] INF-005: DB 백업(WAL) 주기 설정 및 RTO/RPO 복구 파이프라인 구성"
labels: 'feature, priority:medium, infrastructure'
---

## 🎯 Summary
- 기능명: [INF-005] DB 백업(WAL) 주기 설정 및 RTO/RPO 복구 파이프라인 구성
- 목적: 데이터베이스 장애 상황 발생 시 허용 가능한 목표 시간(RTO) 내에 목표 시점(RPO)의 데이터로 복구할 수 있는 안정적인 백업 파이프라인을 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.2.2 (REQ-NF-011)

## 📝 Task Breakdown
- [ ] PostgreSQL의 WAL(Write-Ahead Logging) 아카이빙 활성화 및 S3(또는 지정된 원격 스토리지) 적재 설정.
- [ ] 정기적인 Full Backup (예: 매일 새벽 3시) 스케줄러(pg_dump 또는 AWS RDS Snapshot) 구성.
- [ ] 목표 RPO(≤ 1시간)를 달성하기 위한 WAL 파일 동기화 주기 설정 및 모니터링 연동.
- [ ] 장애 발생 시 백업 데이터(Full + WAL)를 가져와 새로운 인스턴스로 복원하는 RTO(≤ 30분) 복구 스크립트 작성 및 문서화.
- [ ] 복구 파이프라인 작동 여부를 테스트하기 위한 복구 드릴(Recovery Drill) 시나리오 작성.

## ✅ Acceptance Criteria (BDD)
- **Given**: 운영 데이터베이스에 임의의 치명적 장애가 발생한 상황에서
- **When**: 관리자가 사전에 정의된 복구 스크립트(또는 AWS 관리 콘솔 복원)를 실행하면
- **Then**: 장애 발생 시점으로부터 최대 1시간 전(RPO ≤ 1시간)의 상태로, 복구 시작 후 30분 이내(RTO ≤ 30분)에 시스템이 정상 가동 상태로 복원되어야 한다.

## 🛡️ Constraints (NFRs)
- 운영 제약: 백업 작업 자체가 Primary DB의 성능(I/O)에 심각한 영향을 주지 않도록 설정해야 한다.
- 아키텍처 제약: 백업 스토리지(S3 등)는 DB가 위치한 Zone과 물리적으로 격리된 곳에 저장되어야 한다.
