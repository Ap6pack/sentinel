#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_content // .tool_input.content // empty')
[ -z "$FILE" ] && exit 0
case "$FILE" in
  */alembic/versions/*) exit 0 ;;
  *.py) ;;
  *) exit 0 ;;
esac
if echo "$CONTENT" | grep -qE 'execute\(text\(|\.execute\(["'"'"']SELECT'; then
  echo "SENTINEL SQL VIOLATION: raw SQL in ${FILE}" >&2
  echo "Use SQLAlchemy ORM select() constructs, not text() or raw strings." >&2
  echo "Raw SQL only permitted in alembic/versions/. See SKILL-database.md." >&2
  exit 2
fi
exit 0
