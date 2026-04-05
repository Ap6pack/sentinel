#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_content // .tool_input.content // empty')
[ -z "$FILE" ] && exit 0
MODULE=""
case "$FILE" in
  */sentinel_rf/*) MODULE="rf" ;;
  */sentinel_osint/*) MODULE="osint" ;;
  */sentinel_ai/*) MODULE="ai" ;;
  */sentinel_core/*) MODULE="core" ;;
  *) exit 0 ;;
esac
case "$MODULE" in
  rf) FORBIDDEN="sentinel_osint sentinel_ai sentinel_core" ;;
  osint) FORBIDDEN="sentinel_rf sentinel_ai sentinel_core" ;;
  ai) FORBIDDEN="sentinel_rf sentinel_osint sentinel_core" ;;
  core) FORBIDDEN="sentinel_rf sentinel_osint sentinel_ai" ;;
  *) exit 0 ;;
esac
for forbidden in $FORBIDDEN; do
  if echo "$CONTENT" | grep -qE "^(from|import) ${forbidden}"; then
    echo "SENTINEL IMPORT VIOLATION: ${FILE}" >&2
    echo "sentinel-${MODULE} may not import from ${forbidden}." >&2
    echo "Use the event bus or REST API instead. See SKILL-common.md." >&2
    exit 2
  fi
done
exit 0
