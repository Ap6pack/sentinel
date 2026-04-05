#!/bin/bash
cat << 'CONTEXT'
SENTINEL context restored after compaction:

CRITICAL RULES:
1. No module imports another module directly — use bus or REST API
2. All async Python uses asyncio — no threading, no sync I/O in event loop
3. SQLAlchemy: always expire_on_commit=False, never Base.metadata.create_all()
4. No raw SQL text() in app code — only in alembic/versions/ migrations
5. EventEnvelope schema changes require version bump + coordinated deploy
6. Claude API calls always batched (30s window) — never per-event
7. SENTINEL_RF_MOCK=true for hardware-free development

SKILL file index:
  sentinel-common / bus    → SKILL-common.md
  sentinel-rf / decoders   → SKILL-rf.md
  sentinel-osint / linker  → SKILL-osint.md
  sentinel-viz / CesiumJS  → SKILL-viz.md
  sentinel-core / Docker   → SKILL-core.md
  sentinel-ai / Claude API → SKILL-ai.md
  Testing                  → SKILL-testing.md
  Database / Alembic       → SKILL-database.md
  Debugging                → SKILL-debugging.md
  Milestones               → SKILL-phasecheck.md
CONTEXT
git -C "$CLAUDE_PROJECT_DIR" log --oneline -3 2>/dev/null && exit 0
