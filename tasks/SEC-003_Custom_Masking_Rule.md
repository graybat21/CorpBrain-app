---
name: Feature Task
title: "[Feature] SEC-003: 고객사 커스텀 MASKING_RULE 동적 적용 로직"
labels: 'feature, priority:medium, security'
---

## 🎯 Summary
- 기능명: [SEC-003] 고객사 커스텀 MASKING_RULE 동적 적용 로직
- 목적: 글로벌 공통 규칙(주민번호 등) 외에, 고객사가 스스로 지정한 내부 기밀 키워드(예: 신제품 사내 코드명)를 데이터 파이프라인에 동적으로 반영하여 마스킹을 수행한다.

## 🔗 References (Spec & Context)
- SRS 문서: §4.1.4 (REQ-FUNC-016, 017, 018), §4.2.7 (REQ-NF-025)

## 📝 Task Breakdown
- [ ] DB의 `MASKING_RULE` 테이블에서 `is_active=true` 인 해당 `workspace_id`의 커스텀 키워드/정규식 목록을 조회하는 Repository 함수 작성.
- [ ] 매 파이프라인 실행 시 DB 조회를 최적화하기 위해, 커스텀 룰 셋을 메모리(Redis 또는 로컬 캐시)에 캐싱하고 갱신하는(TTL 또는 Pub/Sub 기반) 로직 구현.
- [ ] SEC-001 파이프라인에 커스텀 키워드를 동적으로 컴파일(또는 Aho-Corasick 알고리즘 등 다중 패턴 매칭)하여 마스킹에 추가 적용하는 코드 삽입.
- [ ] 커스텀 규칙이 동적으로 추가(API-W002)되었을 때, 지연시간 1분 이내에 캐시가 무효화되어 파이프라인에 최신 규칙이 적용되도록 연동.

## ✅ Acceptance Criteria (BDD)
- **Given**: 고객사(Workspace A) 관리자가 "오로라프로젝트"라는 키워드를 마스킹 규칙으로 등록한 상태에서
- **When**: 1분 경과 후 해당 고객사의 Slack 채널에 "오로라프로젝트 예산안입니다"라는 메시지가 수집되면
- **Then**: 파이프라인이 동적 룰을 참조하여 "*** 예산안입니다"로 마스킹 처리한 뒤 LLM으로 전송해야 한다.

## 🛡️ Constraints (NFRs)
- 성능 제약: 커스텀 키워드 개수가 늘어나더라도 마스킹 처리 지연시간(Latency)이 선형적으로 급증하지 않도록 O(N) 이하의 최적화된 탐색 알고리즘을 사용해야 한다.
- 아키텍처 제약: 고객사 간 데이터 분리(Multi-tenancy) 규칙을 엄격히 준수하여, A 고객사의 규칙이 B 고객사의 데이터 마스킹에 잘못 적용되지 않아야 한다.
