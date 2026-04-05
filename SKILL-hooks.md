# SKILL: Claude Code hooks & plugins — SENTINEL configuration

## Purpose
This skill covers every Claude Code extension point relevant to SENTINEL:
hooks (lifecycle automation), the project settings file, and the plugin
structure. Read this before touching `.claude/settings.json`, any file in
`.claude/hooks/`, or anything related to how Claude Code behaves in this repo.

The hooks here are not optional polish — they enforce the platform's
non-negotiable rules (no cross-module imports, no sync SQLAlchemy, no raw
SQL, envelope schema stays locked) and automate the quality gates that
would otherwise rely on Claude remembering to run them.

---

## Where config lives

```
sentinel/
├── .claude/
│   ├── settings.json          # Project hooks — committed, applies to all devs
│   ├── settings.local.json    # Personal overrides — gitignored
│   └── hooks/
│       ├── format.sh          # PostToolUse: ruff + prettier after every edit
│       ├── guard-imports.sh   # PreToolUse: block cross-module imports
│       ├── guard-schema.sh    # PostToolUse: detect envelope schema mutations
│       ├── guard-sql.sh       # PreToolUse: block raw SQL strings in app code
│       ├── test-on-stop.sh    # Stop (agent): run tests before declaring done
│       ├── rehydrate.sh       # PostCompact: re-inject critical context
│       └── milestone-check.sh # Stop (agent): verify milestone claims
└── ~/.claude/settings.json    # Personal global hooks (notifications, etc.)
```

---

## The master settings.json

Save this as `.claude/settings.json` in the repo root. It is committed and
applies to every developer and every Claude Code session in this project.

```json
{
  "hooks": {

    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format.sh",
            "timeout": 30
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-schema.sh",
            "timeout": 10
          }
        ]
      }
    ],

    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "if": "Write(packages/sentinel-*/sentinel_*/**/*.py)|Edit(packages/sentinel-*/sentinel_*/**/*.py)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-imports.sh",
            "timeout": 10
          },
          {
            "type": "command",
            "if": "Write(packages/sentinel-*/sentinel_*/**/*.py)|Edit(packages/sentinel-*/sentinel_*/**/*.py)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-sql.sh",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(git push *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-push-check.sh",
            "timeout": 60
          }
        ]
      }
    ],

    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Check if the task just completed involves a milestone claim (e.g. 'M0 complete', 'milestone done', 'phase complete'). If it does, read SKILL-phasecheck.md and run every verification command for that milestone. If any check fails, respond with {\"ok\": false, \"reason\": \"[which check failed and what the output was]\"}. If no milestone was claimed, respond with {\"ok\": true}.",
            "timeout": 120
          }
        ]
      }
    ],

    "PostCompact": [
      {
        "matcher": "auto|manual",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/rehydrate.sh",
            "timeout": 10
          }
        ]
      }
    ],

    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-init.sh",
            "timeout": 15
          }
        ]
      }
    ]

  }
}
```

---

## Hook scripts — full implementations

### format.sh — auto-format after every file edit

```bash
#!/bin/bash
# .claude/hooks/format.sh
# Runs ruff (Python) or prettier (JS/TS) on the file just written.
# Called by PostToolUse on Edit|Write events.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0

case "$FILE" in
  *.py)
    # ruff format then ruff check --fix (lint)
    ruff format --quiet "$FILE" 2>/dev/null
    ruff check --fix --quiet "$FILE" 2>/dev/null
    ;;
  *.js|*.ts|*.jsx|*.tsx|*.json|*.css)
    # prettier — only if config exists
    if [ -f "$CLAUDE_PROJECT_DIR/packages/sentinel-viz/.prettierrc" ] || \
       [ -f "$CLAUDE_PROJECT_DIR/.prettierrc" ]; then
      npx --no-install prettier --write --log-level=silent "$FILE" 2>/dev/null
    fi
    ;;
esac

exit 0
```

### guard-imports.sh — block cross-module imports

```bash
#!/bin/bash
# .claude/hooks/guard-imports.sh
# Blocks Python files that import from a sibling sentinel module directly.
# The rule: no sentinel_X package may import from sentinel_Y package.
# All cross-module communication goes through the bus or REST API.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_content // .tool_input.content // empty')

[ -z "$FILE" ] && exit 0

# Determine which module this file belongs to
MODULE=""
case "$FILE" in
  */sentinel_rf/*) MODULE="rf" ;;
  */sentinel_osint/*) MODULE="osint" ;;
  */sentinel_ai/*) MODULE="ai" ;;
  */sentinel_core/*) MODULE="core" ;;
  */sentinel_viz/*) MODULE="viz" ;;
  *) exit 0 ;;  # Not a module file — skip
esac

# Modules that this module must NOT import from directly
declare -A FORBIDDEN_IMPORTS
FORBIDDEN_IMPORTS["rf"]="sentinel_osint sentinel_ai sentinel_core sentinel_viz"
FORBIDDEN_IMPORTS["osint"]="sentinel_rf sentinel_ai sentinel_core sentinel_viz"
FORBIDDEN_IMPORTS["ai"]="sentinel_rf sentinel_osint sentinel_core sentinel_viz"
FORBIDDEN_IMPORTS["core"]="sentinel_rf sentinel_osint sentinel_ai sentinel_viz"
FORBIDDEN_IMPORTS["viz"]=""  # viz is JS — this guard is for Python only

FORBIDDEN="${FORBIDDEN_IMPORTS[$MODULE]}"
[ -z "$FORBIDDEN" ] && exit 0

# Check the content being written for forbidden imports
for forbidden in $FORBIDDEN; do
  if echo "$CONTENT" | grep -qE "^(from|import) ${forbidden}"; then
    echo "SENTINEL IMPORT VIOLATION: ${FILE}" >&2
    echo "Module sentinel-${MODULE} may not import from ${forbidden}." >&2
    echo "Use the event bus (sentinel_common.bus) or REST API instead." >&2
    echo "See SKILL-common.md for the correct pattern." >&2
    exit 2
  fi
done

exit 0
```

### guard-schema.sh — detect envelope schema mutations

```bash
#!/bin/bash
# .claude/hooks/guard-schema.sh
# Fires after any write to sentinel_common/envelope.py.
# Checks for changes to top-level fields (not payload) which require a
# version bump and coordinated update across all modules.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# Only care about the envelope file
case "$FILE" in
  */sentinel_common/envelope.py) ;;
  *) exit 0 ;;
esac

# Use git diff to see what changed
DIFF=$(git -C "$CLAUDE_PROJECT_DIR" diff HEAD -- "$FILE" 2>/dev/null)
[ -z "$DIFF" ] && exit 0

# Detect new or removed top-level fields (lines starting with field definitions)
# Top-level fields look like: "    id: " or "    ts: " etc.
ADDED=$(echo "$DIFF" | grep -E '^\+\s+(id|ts|source|kind|lat|lon|alt_m|entity_id|payload)\s*:' | head -3)
REMOVED=$(echo "$DIFF" | grep -E '^-\s+(id|ts|source|kind|lat|lon|alt_m|entity_id|payload)\s*:' | head -3)

if [ -n "$ADDED" ] || [ -n "$REMOVED" ]; then
  echo "SENTINEL SCHEMA WARNING: top-level EventEnvelope field change detected." >&2
  echo "" >&2
  echo "This requires a VERSION BUMP in sentinel-common/pyproject.toml" >&2
  echo "AND coordinated update of all consumer modules before deploying." >&2
  echo "" >&2
  echo "See SKILL-common.md section 'Version bumping rules' before proceeding." >&2
  echo "" >&2
  echo "If this is intentional, update the version and continue." >&2
  echo "If this is accidental, revert envelope.py and use payload{} instead." >&2
  # Warning only — exit 0, do not block (agent decides)
fi

exit 0
```

### guard-sql.sh — block raw SQL in application code

```bash
#!/bin/bash
# .claude/hooks/guard-sql.sh
# Blocks writes containing text() raw SQL in non-migration Python files.
# Raw SQL is only permitted in alembic/versions/*.py migration scripts.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_content // .tool_input.content // empty')

[ -z "$FILE" ] && exit 0

# Allow raw SQL in Alembic migrations
case "$FILE" in
  */alembic/versions/*) exit 0 ;;
  *.py) ;;
  *) exit 0 ;;
esac

# Block text() ORM bypass and bare cursor execute
if echo "$CONTENT" | grep -qE 'execute\(text\(|db\.execute\(["'"'"']SELECT|\.execute\(f["'"'"']'; then
  echo "SENTINEL SQL VIOLATION: raw SQL detected in ${FILE}" >&2
  echo "" >&2
  echo "Use SQLAlchemy ORM select() constructs, not text() or raw strings." >&2
  echo "Raw SQL is only permitted in alembic/versions/ migration scripts." >&2
  echo "See SKILL-database.md section 'Writing queries' for the correct pattern." >&2
  exit 2
fi

exit 0
```

### rehydrate.sh — re-inject context after compaction

```bash
#!/bin/bash
# .claude/hooks/rehydrate.sh
# Outputs critical context after context compaction so Claude doesn't forget
# the platform rules. Stdout is injected as a system reminder.

cat << 'CONTEXT'
SENTINEL platform context restored after compaction:

CRITICAL RULES (non-negotiable):
1. No module imports another module directly — use the event bus or REST API
2. All async code uses asyncio — no threading, no sync I/O in event loop
3. Never use expire_on_commit=True in SQLAlchemy sessions
4. Never use Base.metadata.create_all() in production — only Alembic
5. Never write raw SQL text() in application code — only in migrations
6. EventEnvelope schema changes require a version bump + coordinated deploy
7. Never call Claude API in a tight loop — always batch (30s window)
8. All RF mock mode: SENTINEL_RF_MOCK=true bypasses hardware requirement

Current module-to-skill mapping:
- sentinel-common / bus work → read SKILL-common.md
- sentinel-rf / decoders → read SKILL-rf.md
- sentinel-osint / collectors → read SKILL-osint.md
- sentinel-viz / CesiumJS → read SKILL-viz.md
- sentinel-core / auth / Docker → read SKILL-core.md
- sentinel-ai / Claude API → read SKILL-ai.md
- Testing / fixtures / mocks → read SKILL-testing.md
- Database / Alembic → read SKILL-database.md
- Debugging → read SKILL-debugging.md (use decision trees)
- Milestone verification → read SKILL-phasecheck.md (run the commands)
CONTEXT

# Also output the last 3 git commits for context
echo ""
echo "Recent commits:"
git -C "$CLAUDE_PROJECT_DIR" log --oneline -3 2>/dev/null || echo "(no git history)"

exit 0
```

### session-init.sh — inject context at session start

```bash
#!/bin/bash
# .claude/hooks/session-init.sh
# Runs at every session start. Outputs key project status to context.
# Stdout is added to Claude's initial context.

echo "=== SENTINEL session context ==="
echo ""

# Current branch
BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null)
echo "Branch: ${BRANCH:-unknown}"

# Any failing tests (quick check — not full suite)
cd "$CLAUDE_PROJECT_DIR"
FAIL_COUNT=$(python -m pytest packages/ --tb=no -q 2>/dev/null | grep -E "^[0-9]+ failed" | head -1)
if [ -n "$FAIL_COUNT" ]; then
  echo "WARNING: $FAIL_COUNT — fix before adding new code"
else
  echo "Tests: last run clean (or not yet run)"
fi

# Services status
for PORT in 5050 5001 5002 8080; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 1 \
    "http://localhost:${PORT}/api/v1/health" 2>/dev/null)
  case "$STATUS" in
    200) echo "Port ${PORT}: OK" ;;
    000) echo "Port ${PORT}: not running" ;;
    *)   echo "Port ${PORT}: HTTP ${STATUS}" ;;
  esac
done

echo ""
echo "Read CLAUDE.md for skill file index and platform rules."

exit 0
```

### pre-push-check.sh — gate on `git push`

```bash
#!/bin/bash
# .claude/hooks/pre-push-check.sh
# Blocks git push if tests are failing or if ruff reports errors.
# Claude receives the failure output as feedback.

cd "$CLAUDE_PROJECT_DIR"

# Run ruff
RUFF_OUT=$(ruff check packages/ 2>&1)
if [ $? -ne 0 ]; then
  echo "BLOCKED: ruff check failed. Fix lint errors before pushing:" >&2
  echo "$RUFF_OUT" >&2
  exit 2
fi

# Run unit tests
TEST_OUT=$(python -m pytest packages/ -x -q --tb=short 2>&1)
if [ $? -ne 0 ]; then
  echo "BLOCKED: tests failing. Fix before pushing:" >&2
  echo "$TEST_OUT" | tail -30 >&2
  exit 2
fi

echo "Pre-push checks passed." >&2
exit 0
```

---

## Make all hook scripts executable

Run once after cloning:

```bash
chmod +x .claude/hooks/*.sh
```

Add this to the monorepo setup script (`setup.sh` or `Makefile`):

```makefile
# Makefile
hooks:
	chmod +x .claude/hooks/*.sh
	@echo "Hook scripts made executable"
```

---

## Personal global hooks (~/.claude/settings.json)

These go in your home directory — not committed. Add them once per machine.

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude needs input\" with title \"SENTINEL\"'"
          }
        ]
      }
    ],

    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude finished\" with title \"SENTINEL\"' 2>/dev/null; exit 0"
          }
        ]
      }
    ]
  }
}
```

Linux (`notify-send`) version:
```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "notify-send 'SENTINEL' 'Claude needs input'" }]
      }
    ]
  }
}
```

---

## The Stop agent hook — milestone verification in detail

The most powerful hook in this config. When Claude declares a milestone
complete, this agent hook spawns a subagent that reads `SKILL-phasecheck.md`
and runs the actual verification commands. If any check fails, Claude is
told what failed and cannot stop.

How it works:
1. Claude says something like "M3 is complete"
2. The `Stop` agent hook fires
3. A subagent reads SKILL-phasecheck.md, finds the M3 checklist
4. It runs: `redis-cli XRANGE sentinel:events - + COUNT 5 | grep aircraft`,
   checks the Network tab (via bash proxy), confirms no OpenSky calls, etc.
5. If all pass → `{"ok": true}` → Claude stops
6. If any fail → `{"ok": false, "reason": "M3 check 3 failed: OpenSky requests detected in Network tab"}` → Claude must fix it

This is the only reliable way to prevent agents from self-declaring milestones
complete when they have only tested the mock path.

The `stop_hook_active` guard is built into the hook prompt — the agent checks
the input field before running to avoid an infinite loop.

---

## The PostCompact rehydrate hook — why it matters

Claude Code compacts context automatically when the window fills. After
compaction, Claude retains a summary but loses:
- The specific no-cross-module-import rule
- Which skill file to read for which task
- The current branch and failing test count
- Service status

The `rehydrate.sh` hook outputs all of this to stdout immediately after
every compaction. Claude reads it as a system reminder before the next turn.

Without this hook, after a compaction Claude will:
- Write `from sentinel_rf import ...` in sentinel_osint (cross-module import)
- Use `Base.metadata.create_all()` instead of Alembic
- Forget to read the relevant SKILL file before starting work

---

## Debugging hooks

```bash
# See all configured hooks
/hooks    # inside Claude Code CLI

# Test a hook script manually
echo '{"tool_input": {"file_path": "packages/sentinel-rf/sentinel_rf/app.py", "new_content": "from sentinel_osint import x"}}' | \
  .claude/hooks/guard-imports.sh
# Expected: exit 2, stderr message about import violation

# Run with verbose output (Ctrl+O in Claude Code, or):
claude --debug

# Check hook is executable
ls -la .claude/hooks/

# Simulate a PostToolUse event
echo '{"hook_event_name":"PostToolUse","tool_name":"Write","tool_input":{"file_path":"packages/sentinel-rf/sentinel_rf/test.py"}}' | \
  .claude/hooks/format.sh
```

---

## What hooks do NOT replace

Hooks automate enforcement — they do not replace:
- Reading the relevant SKILL file before starting a task
- Running the full test suite (`pytest packages/ -x -q`) at the end of each session
- Manual milestone verification via SKILL-phasecheck.md for non-code milestones
  (e.g. M2 requires visually confirming the globe renders — no hook can do that)
- Code review for changes to sentinel-common (schema changes need human eyes)
