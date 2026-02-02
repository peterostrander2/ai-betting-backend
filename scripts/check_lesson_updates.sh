#!/usr/bin/env bash
set -euo pipefail

# Check if recent commits have user corrections without lesson updates
RECENT_COMMITS=$(git log --since="24 hours ago" --oneline 2>/dev/null || echo "")

if [ -z "$RECENT_COMMITS" ]; then
  echo "✅ No recent commits to check"
  exit 0
fi

if echo "$RECENT_COMMITS" | grep -qiE "fix:|correct|mistake|error|wrong"; then
  LESSONS_UPDATED=$(git log --since="24 hours ago" --name-only 2>/dev/null | grep -q "tasks/lessons.md" && echo "yes" || echo "no")
  
  if [ "$LESSONS_UPDATED" = "no" ]; then
    echo "⚠️  WARNING: Recent commits contain fixes but tasks/lessons.md not updated"
    echo "Consider: Did you learn something that should be captured?"
    exit 0
  fi
fi

echo "✅ Lesson tracking looks good"
