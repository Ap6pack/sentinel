#!/bin/bash
cd "$CLAUDE_PROJECT_DIR"
RUFF_OUT=$(ruff check packages/ 2>&1)
if [ $? -ne 0 ]; then
  echo "BLOCKED: ruff check failed. Fix lint before pushing:" >&2
  echo "$RUFF_OUT" >&2
  exit 2
fi
TEST_OUT=$(python -m pytest packages/ -x -q --tb=short 2>&1)
if [ $? -ne 0 ]; then
  echo "BLOCKED: tests failing. Fix before pushing:" >&2
  echo "$TEST_OUT" | tail -30 >&2
  exit 2
fi
echo "Pre-push checks passed." >&2
exit 0
