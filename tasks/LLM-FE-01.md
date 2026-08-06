---
name: Feature Task
about: SRS 기반의 구체적인 개발 태스크 명세
title: "[Feature] LLM-FE-01: LLM 설정 화면 및 Health Check 상태 표시 UI"
labels: 'feature, frontend, priority:medium'
assignees: ''
---

## :dart: Summary
- 기능명: [LLM-FE-01] LLM 엔진 설정 UI
- 목적: 프론트엔드 환경 설정 페이지에서 Option A/B 엔진 선택 콤보박스를 제공하고 현재 연결 상태(Health)를 시각적 아이콘으로 렌더링한다.

## :link: References (Spec & Context)
- API 명세: API-003, LLM-QRY-01
- **확정 사항: `DEC-16`** — 단가는 사용자 편집 가능 + **기준일 병기**, 비용은 추정치 표기. 엔진 전환은 이 화면의 명시적 선택으로만 발생한다
- **확정 사항: `DEC-12`** — API 키는 `api_key_configured` 불리언만 조회된다 (부분 마스킹 문자열도 받지 않는다)

## :white_check_mark: Task Breakdown (실행 계획)
- [ ] 설정 모달/페이지 내에 Option A/B 선택 UI(콤보박스/라디오 버튼) 마크업
- [ ] 서버에 주기적으로 `GET /api/llm/health` 폴링(Polling)을 수행하여 상태(true/false) 조회
- [ ] 상태에 따라 초록색(✅) 및 붉은색(❌) 신호등 아이콘 컴포넌트 렌더링
- [ ] **단가 편집 UI (`DEC-16`)**: `cloud_price_input_per_mtok` / `cloud_price_output_per_mtok` 입력 필드와 **`cloud_price_updated_at` 기준일 표시**를 함께 배치한다. "공식 가격은 변동하므로 직접 확인해 갱신하세요" 안내를 고정 노출한다
- [ ] **"가격 자동 확인" 기능을 만들지 않는다 (`DEC-15`·`DEC-16`)**: 가격표 조회 버튼·주기적 갱신은 네 번째 egress 목적지가 되므로 UI에 두지 않는다
- [ ] **타임아웃 설정 노출 (`DEC-16`)**: `llm_timeout_read` 등을 고급 설정에서 조정할 수 있게 하고, 저사양 PC의 로컬 추론 지연 시 늘리도록 안내한다
- [ ] **자동 전환 오해 방지 문구**: Health가 ❌여도 앱이 다른 엔진으로 자동 전환하지 않음을 명시한다 (`DEC-16`)

## :test_tube: Acceptance Criteria (BDD/GWT)
Scenario 1: 상태 변경 UI 갱신
- Given: Option A(클라우드)를 선택해둔 상태
- When: 네트워크를 의도적으로 끊음
- Then: Health Check 폴링이 실패하고, 연결 상태 아이콘이 실시간으로 '연결 끊김(❌)'으로 갱신된다.

Scenario 2: 단가 기준일 병기 (DEC-16)
- Given: 마이그레이션 시드 단가와 `cloud_price_updated_at`이 저장되어 있음
- When: 설정 화면을 열고 비용 관련 섹션을 확인함
- Then: 단가 입력 필드와 **기준일이 함께 표시**되고, 비용 표기가 "추정치"임이 명시된다. 가격 자동 확인 버튼은 존재하지 않는다.

## :construction: Dependencies & Blockers
- Depends on: APP-UI-01, API-003, LLM-CMD-01
