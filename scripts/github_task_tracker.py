#!/usr/bin/env python3
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

REPO = "graybat21/CorpBrain-app"

# Mapping from Task Code to GitHub Issue Number.
#
# Issues #1~#68 were filed in alphabetical order of task code, so the mapping is a
# straight sequence. The previous version of this table was hand-written and had 13
# entries pointing at the wrong issue (DB-001 -> #1, but #1 is ANA-CMD-01; API-001 -> #7,
# but #7 is ANA-QRY-01; ...) — the same class of defect that made close_completed_issues.py
# reverse issue states and get itself deleted (see docs/review/CLOSED_ISSUE_AUDIT.md
# appendix A). Since DECISION_LOG rule 2 makes this script the ONLY sanctioned close path,
# a wrong entry here closes a task that was never implemented.
#
# Verified against `gh issue list --state all` on 2026-08-07. Do not edit an entry without
# re-checking the live title: `gh issue view <n> --json title`.
TASK_MAP = {
    "ANA-CMD-01": 1,
    "ANA-CMD-02": 2,
    "ANA-CMD-03": 3,
    "ANA-FE-01": 4,
    "ANA-FE-02": 5,
    "ANA-FE-03": 6,
    "ANA-QRY-01": 7,
    "ANA-QRY-02": 8,
    "ANA-TEST-01": 9,
    "ANA-TEST-02": 10,
    "API-001": 11,
    "API-002": 12,
    "API-003": 13,
    "APP-UI-01": 14,
    "DB-001": 15,
    "DB-002": 16,
    "DL-CMD-01": 17,
    "DL-CMD-02": 18,
    "DL-FE-01": 19,
    "DL-FE-02": 20,
    "DL-QRY-01": 21,
    "DL-TEST-01": 22,
    "INF-CMD-01": 23,
    "INF-CMD-02": 24,
    "INF-TEST-01": 25,
    "INF-TEST-02": 26,
    "LLM-CMD-01": 27,
    "LLM-CMD-02": 28,
    "LLM-CMD-03": 29,
    "LLM-FE-01": 30,
    "LLM-FE-02": 31,
    "LLM-QRY-01": 32,
    "LLM-TEST-01": 33,
    "LLM-TEST-02": 34,
    "MOCK-001": 35,
    "MOCK-002": 36,
    "RN-CMD-01": 37,
    "RN-CMD-02": 38,
    "RN-CMD-03": 39,
    "RN-FE-01": 40,
    "RN-FE-02": 41,
    "RN-QRY-01": 42,
    "RN-TEST-01": 43,
    "SCAN-CMD-01": 44,
    "SCAN-CMD-02": 45,
    "SCAN-QRY-01": 46,
    "SCAN-TEST-01": 47,
    "SCAN-TEST-02": 48,
    "STAT-CMD-01": 49,
    "STAT-FE-01": 50,
    "STAT-QRY-01": 51,
    "STAT-TEST-01": 52,
    "WA-CMD-01": 53,
    "WA-CMD-02": 54,
    "WA-CMD-03": 55,
    "WA-FE-01": 56,
    "WA-FE-02": 57,
    "WA-QRY-01": 58,
    "WA-TEST-01": 59,
    "WA-TEST-02": 60,
    "WS-CMD-01": 61,
    "WS-FE-01": 62,
    "WS-FE-02": 63,
    "WS-FE-03": 64,
    "WS-QRY-01": 65,
    "WS-TEST-01": 66,
    # #67 was never filed; INF-CMD-03 is #68.
    "INF-CMD-03": 68,
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
