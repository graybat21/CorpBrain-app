---
name: Feature Task
title: "[Feature] INF-002: Private Cloud 기반 Gemma LLM 서버 구축"
labels: 'feature, priority:high, infrastructure'
---

## 🎯 Summary
- 기능명: [INF-002] Private Cloud 기반 Gemma LLM 서버 구축
- 목적: 기밀 유출 방지를 위해 외부 LLM API(OpenAI 등)를 배제하고, 독립된 Private Cloud 내에 오픈소스 sLLM(Gemma) 기반의 자체 추론(Self-Hosted) 환경을 구축한다.

## 🔗 References (Spec & Context)
- SRS 문서: §1.5.2 (C-TEC-004)

## 📝 Task Breakdown
- [ ] GPU 가속을 지원하는 Private Cloud 인스턴스(AWS EC2 G-시리즈 또는 등가 인스턴스) 프로비저닝.
- [ ] vLLM, TGI, 또는 Ollama 등을 활용한 Gemma 모델(7B 또는 최적화 버전) 서빙 프레임워크 설치 및 구성.
- [ ] 내부 망(VPC)에서만 LLM 추론 API에 접근할 수 있도록 네트워크 보안 및 포트 제어(Security Group) 설정.
- [ ] LLM 서버의 상태를 체크할 수 있는 `/health` 엔드포인트 노출 및 시스템 서비스(Systemd/Docker) 자동 재시작 등록.
- [ ] 내부 API(API Core)에서 LLM 서버와 통신할 수 있는 Base URL 및 API Key(필요시) 발급 및 공유.

## ✅ Acceptance Criteria (BDD)
- **Given**: 백엔드 시스템(또는 시맨틱 융합 엔진)이 구축된 VPC 내부망에 위치한 상태에서
- **When**: Gemma LLM 서버의 추론 API로 텍스트 요약 프롬프트를 전송하면
- **Then**: 외부 인터넷망(OpenAI 등)을 거치지 않고, 내부 인스턴스에서 자체적으로 처리된 응답이 정상 반환되어야 한다.

## 🛡️ Constraints (NFRs)
- 아키텍처 제약: C-TEC-004 원칙에 따라 데이터 보안 스코프를 유지해야 하므로, LLM 서버는 퍼블릭 IP를 갖지 않거나 철저히 화이트리스트 기반으로 제어되어야 한다.
- 성능 제약: GPU 메모리 한도를 고려하여, 동시 요청 처리(Concurrency) 및 배칭(Batching) 설정이 최적화되어야 한다.
