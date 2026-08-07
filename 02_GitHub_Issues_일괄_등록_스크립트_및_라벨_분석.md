# [Inspection Report] 66개 Task MD 라벨 추출 및 일괄 등록 스크립트 설계서

> **작성일시**: 2026. 8. 6. 오후 2:51:14
> **분석 대상**: `tasks/` 내 마크다운 파일 66개

## 1. 추출된 라벨 (Label Inventory) 및 배정 색상

이슈 생성 전 아래 라벨들이 GitHub 저장소에 생성됩니다.

| 라벨명 (Label) | 배정 색상 (Hex) | 설명/카테고리 |
| :--- | :---: | :--- |
| `api` | #5a32a3 | 일반 기능/테스트 |
| `backend` | #5a32a3 | 백엔드/코어 |
| `daemon` | #ededed | 일반 기능/테스트 |
| `database` | #ededed | 일반 기능/테스트 |
| `feature` | #0366d6 | 프론트엔드 |
| `frontend` | #1d76db | 일반 기능/테스트 |
| `infrastructure` | #ededed | 일반 기능/테스트 |
| `llm` | #ededed | 일반 기능/테스트 |
| `mock` | #fbca04 | 일반 기능/테스트 |
| `os` | #ededed | 일반 기능/테스트 |
| `performance` | #ededed | 일반 기능/테스트 |
| `priority:high` | #d93f0b | 우선순위 |
| `priority:highest` | #d93f0b | 우선순위 |
| `priority:low` | #c5def5 | 우선순위 |
| `priority:medium` | #e99695 | 우선순위 |
| `security` | #ededed | 일반 기능/테스트 |
| `test` | #0e8a16 | 일반 기능/테스트 |
| `vector-db` | #ededed | 일반 기능/테스트 |

## 2. 등록 예정 이슈 목록 요약 (Top 15 및 구조)

총 66개의 태스크가 아래의 정제된 메타데이터로 등록됩니다. (YAML 앞쪽 헤더는 본문에서 제거되어 전송됨)

| Task ID | 파일명 | 추출된 이슈 Title | 적용 라벨 |
| :--- | :--- | :--- | :--- |
| **ANA-CMD-01** | `ANA-CMD-01.md` | [Feature] ANA-CMD-01: 폴더/파일명 추출 및 고속 분석 중요도 산출 후 DB 업데이트 | `feature, backend, priority:high` |
| **ANA-CMD-02** | `ANA-CMD-02.md` | [Feature] ANA-CMD-02: 문서 파싱 후 텍스트 청킹(Chunking) 및 벡터 DB Insert | `feature, backend, priority:high` |
| **ANA-CMD-03** | `ANA-CMD-03.md` | [Feature] ANA-CMD-03: 청크 기반 LLM 위키 마크다운 생성 및 DB Insert | `feature, backend, priority:high, llm` |
| **ANA-FE-01** | `ANA-FE-01.md` | [Feature] ANA-FE-01: 고속 분석 중요도 순 정렬 결과 리스트 렌더링 | `feature, frontend, priority:medium` |
| **ANA-FE-02** | `ANA-FE-02.md` | [Feature] ANA-FE-02: 1-Depth 폴더별 위키 탭 분리 렌더링 | `feature, frontend, priority:high` |
| **ANA-FE-03** | `ANA-FE-03.md` | [Feature] ANA-FE-03: 분석 진행률 프로그레스 바 렌더링 | `feature, frontend, priority:medium` |
| **ANA-QRY-01** | `ANA-QRY-01.md` | [Feature] ANA-QRY-01: 1-Depth 폴더별로 분리 가공된 위키 마크다운 구조 반환 | `feature, backend, priority:medium` |
| **ANA-QRY-02** | `ANA-QRY-02.md` | [Feature] ANA-QRY-02: 분석 진행 상태(Progress) 산출 및 반환 | `feature, backend, priority:medium` |
| **ANA-TEST-01** | `ANA-TEST-01.md` | [Feature] ANA-TEST-01: 지원 4개 포맷 텍스트 추출 정확성 단위 테스트 | `test, backend, priority:medium` |
| **ANA-TEST-02** | `ANA-TEST-02.md` | [Feature] ANA-TEST-02: 위키 문서 격리(Isolation) 1-Depth 침범 검증 테스트 | `test, backend, priority:medium` |
| **API-001** | `API-001.md` | [Feature] API-001: Workspace 도메인 Request/Response DTO 정의 | `feature, api, priority:high` |
| **API-002** | `API-002.md` | [Feature] API-002: Analysis 도메인 Request/Response DTO 정의 | `feature, api, priority:high` |
| **API-003** | `API-003.md` | [Feature] API-003: LLM, Rename, Watcher, Analytics DTO 정의 | `feature, api, priority:high` |
| **APP-UI-01** | `APP-UI-01.md` | [Feature] APP-UI-01: 전체 앱 레이아웃 및 디자인 시스템 기초 공사 | `feature, frontend, priority:highest` |
| **DB-001** | `DB-001.md` | [Feature] DB-001: SQLite `corpbrain_meta.db` 스키마 생성 및 마이그레이션 | `feature, backend, priority:high, database` |
| ... (총 66개) | ... | ... | ... |

## 3. 다음 실행 안내 (Action Details)

GitHub CLI(`gh`)가 설치되고 `gh auth login`으로 인증된 후, 다음 명령어를 실행하면 일괄 등록이 진행됩니다.

```powershell
node register_github_issues.mjs --run
```

- **안정성 보장**: 각 이슈 발급 간 **3.5초의 슬립(Sleep)** 타임이 자동으로 부여되어 GitHub API Rate Limit 및 어뷰징 제재를 원천 방지합니다.
- **결과 기록**: 실행 완료 후 등록된 실제 이슈 번호(#ID) 및 웹 링크가 `03_GitHub_Issues_일괄_등록_실행_결과.md`로 생성됩니다.
