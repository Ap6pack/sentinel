# Contributing to SENTINEL

Thanks for your interest. SENTINEL is open-source under Apache 2.0.

## Before you start

1. Read [CLAUDE.md](CLAUDE.md) — this is the meta-skill file for Claude Code agents and contains the platform rules every contributor needs to understand
2. Read the relevant `SKILL-*.md` file for the module you're working on
3. Check [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the overall design

## Development setup

```bash
git clone https://github.com/Ap6pack/sentinel.git
cd sentinel

# Python packages
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/sentinel-common
pip install -e packages/sentinel-core
pip install -e packages/sentinel-rf
pip install -e packages/sentinel-osint
pip install -e packages/sentinel-ai

# Frontend
cd packages/sentinel-viz && npm install && cd ../..

# Hooks (make scripts executable)
chmod +x .claude/hooks/*.sh

# Environment
cp .env.example .env
# Edit .env — at minimum set SENTINEL_JWT_SECRET and VITE_CESIUM_TOKEN
```

## Running tests

```bash
# Unit tests (no Docker needed)
pytest packages/ -x -q

# With coverage
pytest packages/ --cov=sentinel_common --cov-report=term-missing -q

# Integration tests (requires Docker)
docker compose --profile mock up -d
pytest tests/ -x -q -m integration
```

## Branch and commit conventions

Branches: `feat/{module}/description`, `fix/{module}/description`

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(rf): add AIS vessel decoder
fix(viz): prevent entity leak on rapid reconnect
docs(skill-ai): clarify confidence threshold rules
```

## PR checklist

- [ ] `pytest packages/ -q` passes
- [ ] `ruff check packages/` passes
- [ ] Relevant SKILL file updated if conventions changed
- [ ] At least one test for any new code path
- [ ] No cross-module imports (enforced by `guard-imports.sh` hook)

## Module ownership

| Module | Skill file |
|---|---|
| sentinel-common | SKILL-common.md |
| sentinel-core | SKILL-core.md |
| sentinel-rf | SKILL-rf.md |
| sentinel-osint | SKILL-osint.md |
| sentinel-viz | SKILL-viz.md |
| sentinel-ai | SKILL-ai.md |

## Licence

By contributing, you agree your contributions are licensed under Apache 2.0.
