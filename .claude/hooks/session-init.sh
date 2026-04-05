#!/bin/bash
echo "=== SENTINEL session ==="
BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null)
echo "Branch: ${BRANCH:-unknown}"
for PORT in 5050 5001 5002 8080; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 1 "http://localhost:${PORT}/api/v1/health" 2>/dev/null)
  case "$STATUS" in
    200) echo "Port ${PORT}: OK" ;;
    000) echo "Port ${PORT}: not running" ;;
    *)   echo "Port ${PORT}: HTTP ${STATUS}" ;;
  esac
done
echo "Read CLAUDE.md for platform rules and skill file index."
exit 0
