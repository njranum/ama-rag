#!/usr/bin/env bash
# M1.8-01 — Phase-2 nightly ingestion wrapper for cron.
#
# cron runs with almost no environment (no venv on PATH, arbitrary working directory), so this
# wrapper pins everything itself: it cd's to the repo (so the relative `.chroma/` store and `.env`
# resolve) and invokes the venv's python by absolute path. Secrets come from `.env` (loaded by
# config.load_env), not from cron's environment. Output is appended, timestamped, to `ingest.log`.
#
# NOTE: this wrapper is part of the architecture but is NOT necessarily enabled in local dev — see
# docs/L1_Ingestion.md (Cron / scheduling). Install the crontab entry only when you want nightly
# runs (typically at the production cutover):
#
#   0 0 * * * /Users/snoopy/Dev/rag/scripts/run_ingest.sh
#
# macOS note: cron does not fire while the Mac is asleep; use `launchd` (StartCalendarInterval) if
# catch-up-on-wake matters. Phase 3 replaces this with AWS EventBridge (M4.2-02).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

PYTHON="$REPO_DIR/.venv/bin/python"
LOG="$REPO_DIR/ingest.log"

{
  echo "=== ingest run: $(date '+%Y-%m-%d %H:%M:%S %z') ==="
  "$PYTHON" -m ingest.sync
  echo
} >>"$LOG" 2>&1
