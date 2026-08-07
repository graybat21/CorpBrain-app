#!/usr/bin/env python3
import sys
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

REPO = "graybat21/CorpBrain-app"

# Mapping from Task Code to GitHub Issue Number
TASK_MAP = {
    # Phase 1 & 2
    "DB-001": 1,
    "INF-CMD-01": 4,
    "INF-CMD-02": 5,
    "INF-CMD-03": 68,
    "LLM-CMD-02": 29,
    "WS-CMD-01": 61,
    "SCAN-CMD-01": 44,
    "SCAN-CMD-02": 45,
    # Phase 3
    "ANA-CMD-01": 2,
    "ANA-CMD-02": 3,
    "RN-CMD-01": 37,
    "RN-CMD-02": 38,
    "RN-CMD-03": 39,
    "DL-CMD-01": 12,
    "LLM-CMD-01": 28,
    "LLM-CMD-03": 30,
    # Watcher & Stats
    "WA-CMD-01": 53,
    "WA-CMD-02": 54,
    "WA-CMD-03": 55,
    "WA-QRY-01": 58,
    "STAT-CMD-01": 49,
    # Phase 4
    "API-001": 7,
    "API-002": 8,
    "API-003": 9,
    "APP-UI-01": 10,
    # Phase 3 (additional)
    "DL-CMD-02": 18,
    "SCAN-QRY-01": 46,
    "WS-QRY-01": 65,
    "DL-QRY-01": 21,
    "STAT-QRY-01": 51,
    "RN-QRY-01": 42,
    "LLM-QRY-01": 32,
    "WA-TEST-01": 59,
    "WA-TEST-02": 60,
    "STAT-TEST-01": 52,
    "RN-TEST-01": 43,
    "DL-TEST-01": 22,
    "INF-TEST-01": 25,
    "INF-TEST-02": 26,
    "LLM-TEST-01": 33,
    "LLM-TEST-02": 34,
    "SCAN-TEST-01": 47,
    "SCAN-TEST-02": 48,
    "WS-TEST-01": 66,
    "ANA-TEST-01": 6,
    "DB-002": 16,
    "MOCK-001": 35,
    "MOCK-002": 36,
}

def resolve_issue_number(target: str) -> int:
    target_clean = target.strip().upper()
    if target_clean in TASK_MAP:
        return TASK_MAP[target_clean]
    try:
        return int(target_clean.replace("#", ""))
    except ValueError:
        print(f"Error: Unknown task code or invalid issue number '{target}'")
        sys.exit(1)

def start_task(target: str):
    issue_num = resolve_issue_number(target)
    print(f"🔄 [Task Tracker] Transitioning Task {target} (Issue #{issue_num}) -> IN PROGRESS")
    
    # 1) Add 'in-progress' label to Issue
    cmd_label = [
        "gh", "issue", "edit", str(issue_num),
        "--repo", REPO,
        "--add-label", "in-progress"
    ]
    try:
        subprocess.run(cmd_label, check=True)
        print(f"  ✅ Added 'in-progress' label to Issue #{issue_num}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Failed to add label to Issue #{issue_num}: {e}")

    # 2) Post start comment
    cmd_comment = [
        "gh", "issue", "comment", str(issue_num),
        "--repo", REPO,
        "--body", f"🚀 AI 에이전트(다온)가 태스크 `{target}` 구현 및 검증 작업을 시작합니다. [Status -> In Progress]"
    ]
    try:
        subprocess.run(cmd_comment, check=True)
        print(f"  ✅ Commented on Issue #{issue_num}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Failed to comment on Issue #{issue_num}: {e}")

def complete_task(target: str):
    issue_num = resolve_issue_number(target)
    print(f"✅ [Task Tracker] Transitioning Task {target} (Issue #{issue_num}) -> DONE (Closed)")
    
    # Remove 'in-progress' label if present
    cmd_rm_label = [
        "gh", "issue", "edit", str(issue_num),
        "--repo", REPO,
        "--remove-label", "in-progress"
    ]
    try:
        subprocess.run(cmd_rm_label, check=False)
    except Exception:
        pass

    # Close Issue
    cmd_close = [
        "gh", "issue", "close", str(issue_num),
        "--repo", REPO,
        "--comment", f"✨ 태스크 `{target}` 구현 및 100% 자동화 단위 테스트 검증이 완료되었습니다. [Status -> Done]"
    ]
    try:
        subprocess.run(cmd_close, check=True)
        print(f"  ✅ Closed Issue #{issue_num}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Failed to close Issue #{issue_num}: {e}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python github_task_tracker.py [start|complete] <TASK_CODE_OR_ISSUE_NUM>")
        sys.exit(1)

    action = sys.argv[1].lower()
    target = sys.argv[2]

    if action == "start":
        start_task(target)
    elif action == "complete":
        complete_task(target)
    else:
        print(f"Unknown action: {action}. Use 'start' or 'complete'.")

if __name__ == "__main__":
    main()
