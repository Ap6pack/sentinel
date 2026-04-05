#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
case "$FILE" in
  */sentinel_common/envelope.py) ;;
  *) exit 0 ;;
esac
DIFF=$(git -C "$CLAUDE_PROJECT_DIR" diff HEAD -- "$FILE" 2>/dev/null)
[ -z "$DIFF" ] && exit 0
CHANGED=$(echo "$DIFF" | grep -E '^[+-]\s+(id|ts|source|kind|lat|lon|alt_m|entity_id|payload)\s*:' | head -3)
if [ -n "$CHANGED" ]; then
  echo "SENTINEL SCHEMA WARNING: top-level EventEnvelope field change detected." >&2
  echo "This requires a VERSION BUMP in sentinel-common/pyproject.toml." >&2
  echo "See SKILL-common.md section 'Version bumping rules'." >&2
fi
exit 0
