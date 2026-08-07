# Antigravity 세팅 및 규칙 변환 준비 (CLAUDE.md 기반)

## 1. 개요
기존 `CLAUDE.md`에 명시된 **CorpBrain MVP** 프로젝트의 설계 원칙과 제약사항을 Antigravity 환경에 맞게 적용하기 위한 분석 및 설정 가이드입니다. Antigravity AI가 프로젝트를 진행할 때 절대 어겨서는 안 되는 핵심 규칙들을 추출하고, 이를 Antigravity의 Rule/Instruction 형태로 주입할 수 있도록 정리했습니다.

## 2. Antigravity 맞춤형 핵심 지침 (Project Rules)

Antigravity의 시스템 프롬프트(User Rule)로 주입되어야 할 핵심 제약사항은 다음과 같습니다.

### 2.1. 아키텍처 및 스택 제한 (Strict Boundaries)
- **프론트엔드/패키징**: React SPA(정적 빌드, Tailwind CSS + Shadcn UI, Zustand, react-markdown) + OS-native WebView2 + PyInstaller(`--onefile`). **Node.js 런타임, Electron, Tauri, Next.js, SSR 절대 사용 금지.**
- **데이터베이스 (SQLite)**: 오직 표준 라이브러리 `sqlite3`만 사용. **SQLAlchemy, SQLModel, Alembic, Prisma 도입 절대 금지**. 마이그레이션은 `PRAGMA user_version` 기반으로만 수행.
- **벡터 스토어 (ChromaDB)**: `%LocalAppData%\CorpBrain\vectors\`에 `PersistentClient`로 구성. **FAISS 사용 금지**. 임베딩 로직 내부에 `sentence-transformers`나 `torch` 의존성 추가 절대 금지 (Ollama 외부 API로만 수행).

### 2.2. 데이터 정합성 및 타입 제약
- **ID와 시간**: PK(UUID)는 **TEXT** (36자 소문자 하이픈)로, 시간은 **TEXT ISO-8601 UTC** 포맷(`YYYY-MM-DDTHH:MM:SS.ffffffZ`)으로만 저장. `ON UPDATE CURRENT_TIMESTAMP` 등 MySQL 문법 사용 금지.
- **SSOT 원칙**: 벡터 데이터의 유일한 SSOT는 ChromaDB. SQLite와 ChromaDB의 트랜잭션을 묶을 수 없으므로, 쓰기 순서는 항상 `Chroma delete -> Chroma upsert -> SQLite commit` 순을 유지할 것.

### 2.3. 외부 네트워크 송출 및 보안 (Zero-Telemetry)
- **네트워크 가드**: 외부 네트워크 송출은 오직 `NetworkGuard` 모듈을 통해서만 수행. 타 모듈에서 `httpx`, `requests`, `socket` 임포트 절대 금지. 허용된 목적지(Anthropic, Ollama, 127.0.0.1) 외에 어떠한 원격 원격 텔레메트리 SDK(Sentry, GA 등)도 추가 금지.
- **키 관리**: Anthropic API Key는 오직 Windows DPAPI(`ctypes` 호출)로만 암호화 및 복호화 수행. 메모리에서 즉시 폐기하며, 파일/환경변수/로그에 평문 저장 절대 금지.

### 2.4. PII 마스킹 및 LLM 제약
- **PII 감지**: 정규표현식 기반의 7가지 타입만 감지 (`[PII:TYPE]` 형태). **spaCy, transformers 등의 NER 모델 추가 절대 금지**.
- **LLM 엔진 전환 금지**: Anthropic(Cloud)과 Ollama(Local) 엔진은 사용자의 명시적 설정 변경 없이 절대 자동 스위칭(Fallback)되지 않음.

## 3. Antigravity 룰 주입 방식 제안

Antigravity에서 위의 규칙을 강제하기 위해, 다음과 같은 XML 형태의 룰 스니펫을 `.gemini/config/rules/corpbrain_rule.xml` (또는 프로젝트 로컬 룰 파일)로 구성하여 사용할 것을 권장합니다.

```xml
<RULE[corpbrain_project]>
## CorpBrain MVP 프로젝트 절대 규칙

1. **Tech Stack Limits**: Python `sqlite3`, `fastapi`, `pywebview` / React SPA (Tailwind+Shadcn UI, Zustand) / PyInstaller.
   - 🚫 금지: Node.js 런타임 (Electron/Next.js), ORM (SQLAlchemy/Prisma), in-process ML (torch/spacy), 텔레메트리 SDK.
2. **DB & ChromaDB Rules**:
   - UUID는 TEXT형(36자), DATETIME은 ISO-8601 UTC 문자열로만 저장.
   - 마이그레이션은 `PRAGMA user_version` 기반 raw SQL 파일로 구성.
   - SQLite 쓰기 트랜잭션 내에서 LLM 호출이나 파일 I/O 절대 금지.
3. **Network Security (DEC-15)**:
   - 외부 네트워크 요청은 오직 `NetworkGuard` 단일 모듈만 수행 (httpx, requests 직접 호출 금지).
   - 자격 증명(API Key)은 Windows DPAPI로만 관리.
4. **Data Handling**:
   - 외부 LLM 전송 시 정규식 기반 PII 마스킹(`[PII:TYPE]`) 필수. 파일 절대경로 외부 전송 금지.
   - LLM 엔진 간 자동 Fallback 전환 금지 (명시적 설정에만 의존).
</RULE[corpbrain_project]>
```

## 4. 이후 진행 (Action Items)
1. **Rule 적용**: 위 제안된 `<RULE>` 블록을 Antigravity User Rule에 등록하거나, 프로젝트 디렉토리에 `.antigravitycli/RULES.md` 등의 형태로 반영.
2. **코드 분석 및 연동**: Antigravity가 현재 구현된 코드베이스를 훑어보고(예: `DatabaseManager`, `NetworkGuard` 등) 해당 컨벤션이 올바르게 지켜지고 있는지 정적 검토를 수행할 수 있음.
