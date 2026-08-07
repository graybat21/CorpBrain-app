# [Execution Report] GitHub Issues 일괄 등록 최종 결과

> **실행 일시**: 2026. 8. 6. 오후 3:02:42
> **총 처리 대상**: 66건
> **성공**: 66건 / **실패**: 0건

## 1. 이슈 생성 결과 매핑 테이블

| Task ID | 파일명 | 등록된 이슈 Title | Issue 번호 & Link | 상태 |
| :--- | :--- | :--- | :--- | :---: |
| **ANA-CMD-01** | `ANA-CMD-01.md` | [Feature] ANA-CMD-01: 폴더/파일명 추출 및 고속 분석 중요도 산출 후 DB 업데이트 | [#1](https://github.com/graybat21/CorpBrain-app/issues/1) | 🟢 성공 |
| **ANA-CMD-02** | `ANA-CMD-02.md` | [Feature] ANA-CMD-02: 문서 파싱 후 텍스트 청킹(Chunking) 및 벡터 DB Insert | [#2](https://github.com/graybat21/CorpBrain-app/issues/2) | 🟢 성공 |
| **ANA-CMD-03** | `ANA-CMD-03.md` | [Feature] ANA-CMD-03: 청크 기반 LLM 위키 마크다운 생성 및 DB Insert | [#3](https://github.com/graybat21/CorpBrain-app/issues/3) | 🟢 성공 |
| **ANA-FE-01** | `ANA-FE-01.md` | [Feature] ANA-FE-01: 고속 분석 중요도 순 정렬 결과 리스트 렌더링 | [#4](https://github.com/graybat21/CorpBrain-app/issues/4) | 🟢 성공 |
| **ANA-FE-02** | `ANA-FE-02.md` | [Feature] ANA-FE-02: 1-Depth 폴더별 위키 탭 분리 렌더링 | [#5](https://github.com/graybat21/CorpBrain-app/issues/5) | 🟢 성공 |
| **ANA-FE-03** | `ANA-FE-03.md` | [Feature] ANA-FE-03: 분석 진행률 프로그레스 바 렌더링 | [#6](https://github.com/graybat21/CorpBrain-app/issues/6) | 🟢 성공 |
| **ANA-QRY-01** | `ANA-QRY-01.md` | [Feature] ANA-QRY-01: 1-Depth 폴더별로 분리 가공된 위키 마크다운 구조 반환 | [#7](https://github.com/graybat21/CorpBrain-app/issues/7) | 🟢 성공 |
| **ANA-QRY-02** | `ANA-QRY-02.md` | [Feature] ANA-QRY-02: 분석 진행 상태(Progress) 산출 및 반환 | [#8](https://github.com/graybat21/CorpBrain-app/issues/8) | 🟢 성공 |
| **ANA-TEST-01** | `ANA-TEST-01.md` | [Feature] ANA-TEST-01: 지원 4개 포맷 텍스트 추출 정확성 단위 테스트 | [#9](https://github.com/graybat21/CorpBrain-app/issues/9) | 🟢 성공 |
| **ANA-TEST-02** | `ANA-TEST-02.md` | [Feature] ANA-TEST-02: 위키 문서 격리(Isolation) 1-Depth 침범 검증 테스트 | [#10](https://github.com/graybat21/CorpBrain-app/issues/10) | 🟢 성공 |
| **API-001** | `API-001.md` | [Feature] API-001: Workspace 도메인 Request/Response DTO 정의 | [#11](https://github.com/graybat21/CorpBrain-app/issues/11) | 🟢 성공 |
| **API-002** | `API-002.md` | [Feature] API-002: Analysis 도메인 Request/Response DTO 정의 | [#12](https://github.com/graybat21/CorpBrain-app/issues/12) | 🟢 성공 |
| **API-003** | `API-003.md` | [Feature] API-003: LLM, Rename, Watcher, Analytics DTO 정의 | [#13](https://github.com/graybat21/CorpBrain-app/issues/13) | 🟢 성공 |
| **APP-UI-01** | `APP-UI-01.md` | [Feature] APP-UI-01: 전체 앱 레이아웃 및 디자인 시스템 기초 공사 | [#14](https://github.com/graybat21/CorpBrain-app/issues/14) | 🟢 성공 |
| **DB-001** | `DB-001.md` | [Feature] DB-001: SQLite `corpbrain_meta.db` 스키마 생성 및 마이그레이션 | [#15](https://github.com/graybat21/CorpBrain-app/issues/15) | 🟢 성공 |
| **DB-002** | `DB-002.md` | [Feature] DB-002: ChromaDB / FAISS 벡터 DB 컬렉션 초기화 스크립트 작성 | [#16](https://github.com/graybat21/CorpBrain-app/issues/16) | 🟢 성공 |
| **DL-CMD-01** | `DL-CMD-01.md` | [Feature] DL-CMD-01: 위키 문장과 `File_Meta` 간 매핑(Anchor) 식별자 DB Update | [#17](https://github.com/graybat21/CorpBrain-app/issues/17) | 🟢 성공 |
| **DL-CMD-02** | `DL-CMD-02.md` | [Feature] DL-CMD-02: IPC 기반 `os.startfile` 호출 로직 구현 | [#18](https://github.com/graybat21/CorpBrain-app/issues/18) | 🟢 성공 |
| **DL-FE-01** | `DL-FE-01.md` | [Feature] DL-FE-01: 위키 뷰어 내 딥링크 배지 렌더링 및 깨진 링크 시 회색/툴팁 처리 | [#19](https://github.com/graybat21/CorpBrain-app/issues/19) | 🟢 성공 |
| **DL-FE-02** | `DL-FE-02.md` | [Feature] DL-FE-02: 딥링크 onClick 시 브라우저 기본 동작 차단 및 IPC(Command) 호출 | [#20](https://github.com/graybat21/CorpBrain-app/issues/20) | 🟢 성공 |
| **DL-QRY-01** | `DL-QRY-01.md` | [Feature] DL-QRY-01: 위키 내 딥링크 대상 원본 파일의 현재 존재(Broken) 여부 검증 반환 | [#21](https://github.com/graybat21/CorpBrain-app/issues/21) | 🟢 성공 |
| **DL-TEST-01** | `DL-TEST-01.md` | [Feature] DL-TEST-01: Broken Link 실시간 검증 단위 테스트 | [#22](https://github.com/graybat21/CorpBrain-app/issues/22) | 🟢 성공 |
| **INF-CMD-01** | `INF-CMD-01.md` | [Feature] INF-CMD-01: Windows `MAX_PATH` 초과 및 권한 거부 글로벌 예외 처리 | [#23](https://github.com/graybat21/CorpBrain-app/issues/23) | 🟢 성공 |
| **INF-CMD-02** | `INF-CMD-02.md` | [Feature] INF-CMD-02: 로그 파일 로테이션 (50MB/30일) 및 Config 포팅 (JSON) | [#24](https://github.com/graybat21/CorpBrain-app/issues/24) | 🟢 성공 |
| **INF-TEST-01** | `INF-TEST-01.md` | [Feature] INF-TEST-01: 1,000개 파일 스캔 시 p95 < 5,000ms 성능 부하 테스트 | [#25](https://github.com/graybat21/CorpBrain-app/issues/25) | 🟢 성공 |
| **INF-TEST-02** | `INF-TEST-02.md` | [Feature] INF-TEST-02: 외부 클라우드(Telemetry) 통신 완전 격리 테스트 | [#26](https://github.com/graybat21/CorpBrain-app/issues/26) | 🟢 성공 |
| **LLM-CMD-01** | `LLM-CMD-01.md` | [Feature] LLM-CMD-01: LLM 엔진 설정(Option A/B) 변경 및 DB 저장 | [#27](https://github.com/graybat21/CorpBrain-app/issues/27) | 🟢 성공 |
| **LLM-CMD-02** | `LLM-CMD-02.md` | [Feature] LLM-CMD-02: Option A 전송 전 PII 마스킹 인메모리 적용 | [#28](https://github.com/graybat21/CorpBrain-app/issues/28) | 🟢 성공 |
| **LLM-CMD-03** | `LLM-CMD-03.md` | [Feature] LLM-CMD-03: Option B 선택 시 Ollama 데몬 무인 설치 및 백그라운드 모델 Pull | [#29](https://github.com/graybat21/CorpBrain-app/issues/29) | 🟢 성공 |
| **LLM-FE-01** | `LLM-FE-01.md` | [Feature] LLM-FE-01: LLM 설정 화면 및 Health Check 상태 표시 UI | [#30](https://github.com/graybat21/CorpBrain-app/issues/30) | 🟢 성공 |
| **LLM-FE-02** | `LLM-FE-02.md` | [Feature] LLM-FE-02: Ollama 설치 프로그레스 및 Health Check 상태 아이콘 | [#31](https://github.com/graybat21/CorpBrain-app/issues/31) | 🟢 성공 |
| **LLM-QRY-01** | `LLM-QRY-01.md` | [Feature] LLM-QRY-01: 선택된 엔진(Cloud/Ollama) 연결 상태 확인 (Health Check) 반환 | [#32](https://github.com/graybat21/CorpBrain-app/issues/32) | 🟢 성공 |
| **LLM-TEST-01** | `LLM-TEST-01.md` | [Feature] LLM-TEST-01: PII 마스킹 단위 테스트 및 마스킹 실패 예외 검증 | [#33](https://github.com/graybat21/CorpBrain-app/issues/33) | 🟢 성공 |
| **LLM-TEST-02** | `LLM-TEST-02.md` | [Feature] LLM-TEST-02: LLM Health Check 단위 테스트 | [#34](https://github.com/graybat21/CorpBrain-app/issues/34) | 🟢 성공 |
| **MOCK-001** | `MOCK-001.md` | [Feature] MOCK-001: 프론트엔드 UI 독립 개발용 Workspace 및 대시보드 Mock 서버 세팅 | [#35](https://github.com/graybat21/CorpBrain-app/issues/35) | 🟢 성공 |
| **MOCK-002** | `MOCK-002.md` | [Feature] MOCK-002: 심층 분석 결과(폴더별 탭) 및 Rename Diff 반환 Mock 서버 세팅 | [#36](https://github.com/graybat21/CorpBrain-app/issues/36) | 🟢 성공 |
| **RN-CMD-01** | `RN-CMD-01.md` | [Feature] RN-CMD-01: LLM 템플릿 추천 호출 및 Diff 결과를 DB에 임시 저장 | [#37](https://github.com/graybat21/CorpBrain-app/issues/37) | 🟢 성공 |
| **RN-CMD-02** | `RN-CMD-02.md` | [Feature] RN-CMD-02: 승인된 Diff 기반 OS 레벨 물리 파일 Rename 및 내역 확정 | [#38](https://github.com/graybat21/CorpBrain-app/issues/38) | 🟢 성공 |
| **RN-CMD-03** | `RN-CMD-03.md` | [Feature] RN-CMD-03: `Rename_History` 기록 기반 OS 파일명 100% 원복(Undo) 실행 | [#39](https://github.com/graybat21/CorpBrain-app/issues/39) | 🟢 성공 |
| **RN-FE-01** | `RN-FE-01.md` | [Feature] RN-FE-01: Rename Diff 미리보기 테이블 렌더링 | [#40](https://github.com/graybat21/CorpBrain-app/issues/40) | 🟢 성공 |
| **RN-FE-02** | `RN-FE-02.md` | [Feature] RN-FE-02: Apply 및 Undo 버튼 동작 및 실패 모달 렌더링 | [#41](https://github.com/graybat21/CorpBrain-app/issues/41) | 🟢 성공 |
| **RN-QRY-01** | `RN-QRY-01.md` | [Feature] RN-QRY-01: 생성된 파일명 Diff (Old/New) 매핑 리스트 반환 | [#42](https://github.com/graybat21/CorpBrain-app/issues/42) | 🟢 성공 |
| **RN-TEST-01** | `RN-TEST-01.md` | [Feature] RN-TEST-01: Rename Undo 100% 원복 통합 테스트 | [#43](https://github.com/graybat21/CorpBrain-app/issues/43) | 🟢 성공 |
| **SCAN-CMD-01** | `SCAN-CMD-01.md` | [Feature] SCAN-CMD-01: 파일 트리 순회 및 블랙리스트 제외 후 `File_Meta` 벌크 Insert | [#44](https://github.com/graybat21/CorpBrain-app/issues/44) | 🟢 성공 |
| **SCAN-CMD-02** | `SCAN-CMD-02.md` | [Feature] SCAN-CMD-02: 파일 수 10,000개 도달 시 순회 중단 및 Limit Guard 예외 반환 | [#45](https://github.com/graybat21/CorpBrain-app/issues/45) | 🟢 성공 |
| **SCAN-QRY-01** | `SCAN-QRY-01.md` | [Feature] SCAN-QRY-01: 스캔된 파일 수, 용량(MB), 예상 소요시간 산출 후 반환 | [#46](https://github.com/graybat21/CorpBrain-app/issues/46) | 🟢 성공 |
| **SCAN-TEST-01** | `SCAN-TEST-01.md` | [Feature] SCAN-TEST-01: 스캔 필터링(블랙리스트) 단위 테스트 | [#47](https://github.com/graybat21/CorpBrain-app/issues/47) | 🟢 성공 |
| **SCAN-TEST-02** | `SCAN-TEST-02.md` | [Feature] SCAN-TEST-02: 스캔 Limit Guard (10K 제한) 단위 테스트 | [#48](https://github.com/graybat21/CorpBrain-app/issues/48) | 🟢 성공 |
| **STAT-CMD-01** | `STAT-CMD-01.md` | [Feature] STAT-CMD-01: 통계 이벤트 발생 시 수치 로깅 및 DB Insert | [#49](https://github.com/graybat21/CorpBrain-app/issues/49) | 🟢 성공 |
| **STAT-FE-01** | `STAT-FE-01.md` | [Feature] STAT-FE-01: My Analytics 차트 및 4대 지표 대시보드 UI 렌더링 | [#50](https://github.com/graybat21/CorpBrain-app/issues/50) | 🟢 성공 |
| **STAT-QRY-01** | `STAT-QRY-01.md` | [Feature] STAT-QRY-01: WPM 기반 통계 산출 | [#51](https://github.com/graybat21/CorpBrain-app/issues/51) | 🟢 성공 |
| **STAT-TEST-01** | `STAT-TEST-01.md` | [Feature] STAT-TEST-01: WPM 기반 절약 시간 산출 단위 테스트 | [#52](https://github.com/graybat21/CorpBrain-app/issues/52) | 🟢 성공 |
| **WA-CMD-01** | `WA-CMD-01.md` | [Feature] WA-CMD-01: Watcher 설정 모드(수동/실시간/유휴) 변경 및 DB 저장 | [#53](https://github.com/graybat21/CorpBrain-app/issues/53) | 🟢 성공 |
| **WA-CMD-02** | `WA-CMD-02.md` | [Feature] WA-CMD-02: `watchdog` 이벤트 감지, 디바운싱 및 타임스탬프 대조 로직 | [#54](https://github.com/graybat21/CorpBrain-app/issues/54) | 🟢 성공 |
| **WA-CMD-03** | `WA-CMD-03.md` | [Feature] WA-CMD-03: 내용이 수정된 파일 재분석 및 위키 부분 재생성 후 DB 갱신 | [#55](https://github.com/graybat21/CorpBrain-app/issues/55) | 🟢 성공 |
| **WA-FE-01** | `WA-FE-01.md` | [Feature] WA-FE-01: UI 설정 콤보박스 및 상태 아이콘 렌더링 | [#56](https://github.com/graybat21/CorpBrain-app/issues/56) | 🟢 성공 |
| **WA-FE-02** | `WA-FE-02.md` | [Feature] WA-FE-02: 백그라운드 위키 갱신 성공 시 IPC Toast 알림 렌더링 | [#57](https://github.com/graybat21/CorpBrain-app/issues/57) | 🟢 성공 |
| **WA-QRY-01** | `WA-QRY-01.md` | [Feature] WA-QRY-01: Watcher 상태 및 큐 대기 건수 반환 | [#58](https://github.com/graybat21/CorpBrain-app/issues/58) | 🟢 성공 |
| **WA-TEST-01** | `WA-TEST-01.md` | [Feature] WA-TEST-01: Watcher 이벤트 디바운싱 및 필터링 단위 테스트 | [#59](https://github.com/graybat21/CorpBrain-app/issues/59) | 🟢 성공 |
| **WA-TEST-02** | `WA-TEST-02.md` | [Feature] WA-TEST-02: 유휴(Idle) 모드 Watcher 통합 테스트 | [#60](https://github.com/graybat21/CorpBrain-app/issues/60) | 🟢 성공 |
| **WS-CMD-01** | `WS-CMD-01.md` | [Feature] WS-CMD-01: 2개 이상 로컬 폴더 병합 및 `Workspace_Meta` DB 레코드 삽입 | [#61](https://github.com/graybat21/CorpBrain-app/issues/61) | 🟢 성공 |
| **WS-FE-01** | `WS-FE-01.md` | [Feature] WS-FE-01: 좌측 히스토리 패널 렌더링 및 워크스페이스 목록 연동 | [#62](https://github.com/graybat21/CorpBrain-app/issues/62) | 🟢 성공 |
| **WS-FE-02** | `WS-FE-02.md` | [Feature] WS-FE-02: 워크스페이스 생성 모달 및 OS 폴더 선택기 연동 | [#63](https://github.com/graybat21/CorpBrain-app/issues/63) | 🟢 성공 |
| **WS-FE-03** | `WS-FE-03.md` | [Feature] WS-FE-03: 대시보드 통계 바인딩 및 예외 수신 알림 다이얼로그 표시 | [#64](https://github.com/graybat21/CorpBrain-app/issues/64) | 🟢 성공 |
| **WS-QRY-01** | `WS-QRY-01.md` | [Feature] WS-QRY-01: 전체 워크스페이스 목록 및 단일 상세 조회 로직 | [#65](https://github.com/graybat21/CorpBrain-app/issues/65) | 🟢 성공 |
| **WS-TEST-01** | `WS-TEST-01.md` | [Feature] WS-TEST-01: 폴더 병합 비즈니스 로직 단위 테스트 및 앱 재시작 영속성 통합 테스트 | [#66](https://github.com/graybat21/CorpBrain-app/issues/66) | 🟢 성공 |
