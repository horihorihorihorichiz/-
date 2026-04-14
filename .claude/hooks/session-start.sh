#!/bin/bash
#
# SessionStart hook for the Slides-to-Web (PowerPoint auto-creation) project.
#
# Installs Node dependencies (puppeteer + pptxgenjs) so that `npm run export`
# is ready to convert slides/index.html into slides/exports/presentation.pptx
# the moment the session starts.
#
set -euo pipefail

# Only run in Claude Code on the web (remote) environments.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"

echo "[session-start] Installing npm dependencies for slide → PPTX export..."

# Use `npm install` (not `npm ci`) so the cached container state is reused
# across sessions and re-runs are fast and idempotent.
npm install --no-audit --no-fund

echo "[session-start] Dependencies ready."
echo "[session-start] Preview:  npm run preview"
echo "[session-start] Export:   npm run export"
