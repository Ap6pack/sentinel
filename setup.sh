#!/bin/bash
# setup.sh — one-time development environment setup for SENTINEL
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         SENTINEL setup               ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Environment file ──────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  # Generate a random JWT secret
  JWT=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i.bak "s/^SENTINEL_JWT_SECRET=$/SENTINEL_JWT_SECRET=$JWT/" .env
  rm -f .env.bak
  echo "✓ Created .env with generated JWT secret"
  echo "  → Add your VITE_CESIUM_TOKEN and ANTHROPIC_API_KEY to .env before starting"
else
  echo "✓ .env already exists"
fi

# ── Python venv ───────────────────────────────────────────────────────────────
if [ ! -d .venv ]; then
  python3 -m venv .venv
  echo "✓ Created .venv"
fi

source .venv/bin/activate

echo "Installing Python packages..."
pip install --quiet -e packages/sentinel-common
pip install --quiet -e packages/sentinel-core
pip install --quiet -e packages/sentinel-rf
pip install --quiet -e packages/sentinel-osint
pip install --quiet -e packages/sentinel-ai
echo "✓ Python packages installed"

# ── Frontend ──────────────────────────────────────────────────────────────────
if [ -d packages/sentinel-viz ]; then
  echo "Installing frontend packages..."
  cd packages/sentinel-viz
  npm install --silent
  cd ../..
  echo "✓ Frontend packages installed"

  # Create viz .env.local if missing
  if [ ! -f packages/sentinel-viz/.env.local ]; then
    cat > packages/sentinel-viz/.env.local << 'ENVLOCAL'
# Get your free token at https://ion.cesium.com/
VITE_CESIUM_TOKEN=
VITE_WS_URL=ws://localhost:8080/ws/stream
VITE_OSINT_API=http://localhost:8080/api/osint
ENVLOCAL
    echo "✓ Created packages/sentinel-viz/.env.local"
    echo "  → Add your VITE_CESIUM_TOKEN to packages/sentinel-viz/.env.local"
  fi
fi

# ── Hook scripts ──────────────────────────────────────────────────────────────
chmod +x .claude/hooks/*.sh 2>/dev/null || true
echo "✓ Hook scripts made executable"

# ── Verify imports ────────────────────────────────────────────────────────────
python3 -c "
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from sentinel_common.bus import BusPublisher, BusConsumer
from sentinel_common.geo import haversine_m
print('✓ sentinel-common imports OK')
"

echo ""
echo "══════════════════════════════════════════"
echo "  Setup complete. Next steps:"
echo ""
echo "  1. Add VITE_CESIUM_TOKEN to .env"
echo "     (free at https://ion.cesium.com/)"
echo ""
echo "  2. Start the stack:"
echo "     docker compose --profile basic up -d"
echo ""
echo "  3. Open http://localhost:8080"
echo ""
echo "  No SDR hardware? Set SENTINEL_RF_MOCK=true in .env"
echo "══════════════════════════════════════════"
