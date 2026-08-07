#!/usr/bin/env bash
# tasks/*.md 변경분을 기존 GitHub Issue 본문에 동기화한다.
#
# - task 카드의 YAML frontmatter를 제외한 본문 전체를 Issue body로 덮어쓴다.
#   (register_github_issues.mjs 의 등록 규칙과 동일)
# - frontmatter 의 title 이 바뀐 카드는 Issue title 도 함께 갱신한다.
# - API rate limit 회피를 위해 호출 간 1.5초 sleep.
#
# 사용법: bash scripts/sync_task_issues.sh <TASK_ID>:<ISSUE_NUMBER> [...]
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <TASK_ID>:<ISSUE_NUMBER> [...]" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMPDIR_BODY="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_BODY"' EXIT

for pair in "$@"; do
  task_id="${pair%%:*}"
  issue_no="${pair##*:}"
  card="$REPO_ROOT/tasks/$task_id.md"

  if [ ! -f "$card" ]; then
    echo "SKIP  $task_id — 카드 파일 없음: $card" >&2
    continue
  fi

  # frontmatter(두 번째 '---' 까지)를 제외한 본문 추출
  body_file="$TMPDIR_BODY/$task_id.body.md"
  awk 'BEGIN{d=0} /^---[[:space:]]*$/{d++; if(d<=2) next} d>=2{print}' "$card" \
    | sed '/./,$!d' > "$body_file"

  if [ ! -s "$body_file" ]; then
    echo "SKIP  $task_id — 추출된 본문이 비어 있음" >&2
    continue
  fi

  # frontmatter title 추출 (앞뒤 따옴표 제거)
  title="$(awk -F': ' '/^title:/{sub(/^title:[[:space:]]*/,""); gsub(/^"|"$/,""); print; exit}' "$card")"

  if [ -n "$title" ]; then
    gh issue edit "$issue_no" --title "$title" --body-file "$body_file" >/dev/null
  else
    gh issue edit "$issue_no" --body-file "$body_file" >/dev/null
  fi

  echo "OK    #$issue_no  <- tasks/$task_id.md"
  sleep 1.5
done

echo "동기화 완료."
