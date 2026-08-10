#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# VM Update & Redeploy Script — AI Fashion Designer
# Runs on the GCE VM to update code, build frontend, restart backend,
# and verify system health.
#
# Usage (on VM):
#   bash scripts/vm-update.sh [branch_name]
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/srv/ai-fashion-designer/app"
BRANCH="${1:-main}"

echo "═══════════════════════════════════════════════════════"
echo "  AI Fashion Designer — VM Update & Deployment"
echo "  Target Branch: ${BRANCH}"
echo "═══════════════════════════════════════════════════════"
echo ""

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Error: App directory $APP_DIR does not exist. Run vm-setup.sh first."
    exit 1
fi

cd "$APP_DIR"

# ─── 1. Git Update ───
echo "▶ [1/5] Pulling latest code from git..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# ─── 2. Python Dependencies ───
echo "▶ [2/5] Updating Python virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate
else
    echo "⚠️ Warning: venv not found. Creating new venv..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
fi

# ─── 3. Build & Deploy Frontend ───
echo "▶ [3/5] Building React frontend..."
cd "$APP_DIR/frontend"
npm install --quiet
npm run build --quiet

echo "  Copying static build to /var/www/ai-fashion-designer..."
sudo mkdir -p /var/www/ai-fashion-designer
sudo cp -r dist/* /var/www/ai-fashion-designer/

# ─── 4. Restart Backend & Nginx ───
echo "▶ [4/5] Restarting backend service & Nginx..."
sudo systemctl restart ai-fashion-backend
sudo systemctl reload nginx

# ─── 5. Health Verification ───
echo "▶ [5/5] Verifying API Health..."
HEALTH_STATUS="000"
for i in {1..5}; do
    sleep 2
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8083/v1/health || echo "000")
    if [ "$HEALTH_STATUS" -eq 200 ]; then
        break
    fi
    echo "  Waiting for uvicorn worker initialization... (Attempt $i/5)"
done

if [ "$HEALTH_STATUS" -eq 200 ]; then
    echo "  ✅ Backend Health Check PASSED (HTTP 200)"
else
    echo "  ❌ Backend Health Check FAILED (HTTP $HEALTH_STATUS)"
    echo "  Checking service logs..."
    sudo journalctl -u ai-fashion-backend -n 20 --no-pager
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  🚀 Deployment Completed Successfully!"
echo "  Live URL: https://8.234.93.21.nip.io/"
echo "═══════════════════════════════════════════════════════"
