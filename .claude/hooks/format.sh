#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0
case "$FILE" in
  *.py)
    ruff format --quiet "$FILE" 2>/dev/null
    ruff check --fix --quiet "$FILE" 2>/dev/null
    ;;
  *.js|*.ts|*.jsx|*.tsx|*.json|*.css)
    if [ -f "$CLAUDE_PROJECT_DIR/packages/sentinel-viz/.prettierrc" ] || [ -f "$CLAUDE_PROJECT_DIR/.prettierrc" ]; then
      npx --no-install prettier --write --log-level=silent "$FILE" 2>/dev/null
    fi
    ;;
esac
exit 0
