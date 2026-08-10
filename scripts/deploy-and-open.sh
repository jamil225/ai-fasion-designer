#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# Local One-Touch Deploy & Launch Script — AI Fashion Designer
# Runs on your LOCAL workstation (Mac).
# SSHs into GCP VM, updates code, rebuilds, restarts services,
# and automatically opens the live HTTPS URL in your browser!
#
# Usage:
#   chmod +x scripts/deploy-and-open.sh
#   ./scripts/deploy-and-open.sh [branch_name]
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

GCP_ZONE="asia-south1-a"
GCP_INSTANCE="ai-fashion-designer"
GCP_PROJECT="peopleverdict-696f3"
BRANCH="${1:-main}"
LIVE_URL="https://8.234.93.21.nip.io/"

echo "═══════════════════════════════════════════════════════"
echo "  AI Fashion Designer — One-Touch Deploy & Launch"
echo "  Target Branch: ${BRANCH}"
echo "═══════════════════════════════════════════════════════"
echo ""

echo "▶ [1/3] Triggering remote deployment on GCP VM via gcloud SSH..."
gcloud compute ssh "$GCP_INSTANCE" \
    --zone="$GCP_ZONE" \
    --project="$GCP_PROJECT" \
    --command="bash /srv/ai-fashion-designer/app/scripts/vm-update.sh ${BRANCH}"

echo ""
echo "▶ [2/3] Verifying remote HTTPS endpoint status..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$LIVE_URL/v1/health" || echo "000")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "  ✅ Live Health Check: HTTP 200 OK"
else
    echo "  ⚠️ Remote endpoint returned HTTP $HTTP_CODE (or self-signed SSL warning)."
fi

echo ""
echo "▶ [3/3] Opening live web application in browser..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$LIVE_URL"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "$LIVE_URL" 2>/dev/null || echo "Please open manually: $LIVE_URL"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    start "$LIVE_URL"
else
    echo "Please open manually: $LIVE_URL"
fi

echo ""
echo "✨ All Done! App launched at $LIVE_URL"
