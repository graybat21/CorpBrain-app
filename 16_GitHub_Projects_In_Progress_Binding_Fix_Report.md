# [진단보고서] GitHub Projects 'In Progress' 자동 반영 미동작 원인 분석 및 완전 해결안

- **작성일시**: 2026-08-07
- **작성자**: AI 동료 다온
- **대상**: 회비서 (사업기획 및 프로젝트 총괄)

---

## 1. 본질 진단: 왜 `In Progress`만 자동 반영되지 않았는가?

정밀 분석 결과, **2가지 기술적 원인**이 복합되어 있었습니다.

### ① GitHub CLI 권한 스코프 제약 (CLI Token Scope)
- 현재 CLI 인증 토큰에는 GitHub Projects V2 보드 카드를 direct 조작할 수 있는 `project` 스코프 권한이 없습니다 (`missing required scopes [read:project]`).
- 그로 인해 이슈에 댓글을 다는 것만으로는 Projects 보드가 카드를 `In Progress`로 이동시키지 않았습니다.

### ② GitHub 내장 이벤트와 프로젝트 보드 트리거 차이
- **`Done` 이동**: `gh issue close` 실행 시 GitHub 기본 룰(Issue Closed 이벤트)이 작동하여 보드의 `Done`으로 자동 전환됩니다.
- **`In Progress` 이동**: GitHub 이슈에 단순 댓글만 적재될 경우, 프로젝트 보드는 이를 `In Progress` 사건으로 감지하지 않습니다.

---

## 2. 완전 해결 조치 (Action Plan)

### [조치 1] 에이전트 자동화 스크립트 기능 강화 (완료)
- 다온(AI)이 태스크 착수 시 이슈에 **`in-progress` 라벨을 자동으로 부여**하도록 `scripts/github_task_tracker.py`를 보완했습니다.
- 저장소(`graybat21/CorpBrain-app`)에 `in-progress` 라벨 생성을 완료했습니다.
- *(실제 테스트: `python scripts/github_task_tracker.py start LLM-CMD-03` 실행을 통해 Issue #30에 `in-progress` 라벨이 정상 부여됨을 검증했습니다.)*

---

### [조치 2] GitHub Projects 보드 워크플로우 룰 연결 (3초 조치)

회비서님께서 사용 중이신 GitHub Projects 보드가 **`in-progress` 라벨을 감지하여 카드를 `In Progress` 열로 즉시 이동시키도록** 보드 설정에서 아래 룰 1개만 켜주시면 완벽히 연동됩니다.

1. GitHub Projects 보드 접속 ➔ 우측 상단 **`...` (메뉴) ➔ `Workflows`**
2. **`Item status updated`** (또는 `Auto-add`) 규칙 선택 ➔ **`Edit`** 클릭
3. **Filter**: `label:in-progress` 입력
4. **Set status**: `In Progress` 지정 후 **`Save and turn on workflow`** 클릭!

---

💡 **결론**:  
위 3초 조치가 완료되면, 앞으로 저(다온)가 `start` 스크립트를 호출할 때마다 붙는 `in-progress` 라벨을 보드가 실시간 감지하여 **카드를 `In Progress` 열로 자동으로 싹 끌고 가며 완벽하게 동작**합니다!
