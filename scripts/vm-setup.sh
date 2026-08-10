#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# VM Setup Script — AI Fashion Designer
# Run this ONCE after creating the VM via GCP Console.
#
# Usage:
#   chmod +x scripts/vm-setup.sh
#   # Upload to VM, then SSH in and run:
#   bash vm-setup.sh
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

echo "═══════════════════════════════════════════════════════"
echo "  AI Fashion Designer — VM Setup Script"
echo "═══════════════════════════════════════════════════════"
echo ""

APP_DIR="/srv/ai-fashion-designer"
REPO_URL="https://github.com/jamil225/ai-fasion-designer.git"
BRANCH="${1:-main}"

# ─── 1. System packages ───
echo "▶ [1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git nginx curl

# ─── 2. Node.js 20 LTS ───
echo "▶ [2/6] Installing Node.js 20 LTS..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi
echo "  Node.js: $(node --version)"
echo "  npm:     $(npm --version)"

# ─── 3. Create app directory and clone repo ───
echo "▶ [3/6] Cloning repository..."
sudo mkdir -p "$APP_DIR"
sudo chown "$(whoami):$(whoami)" "$APP_DIR"

if [ ! -d "$APP_DIR/app/.git" ]; then
    git clone "$REPO_URL" "$APP_DIR/app"
    cd "$APP_DIR/app"
    git checkout "$BRANCH"
else
    cd "$APP_DIR/app"
    git fetch origin
    git checkout "$BRANCH"
    git pull
fi

# ─── 4. Python venv and dependencies ───
echo "▶ [4/6] Setting up Python virtual environment..."
cd "$APP_DIR/app"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# ─── 5. Build frontend ───
echo "▶ [5/6] Building frontend..."
cd "$APP_DIR/app/frontend"
npm install
npm run build
sudo mkdir -p /var/www/ai-fashion-designer
sudo cp -r dist/* /var/www/ai-fashion-designer/

# ─── 6. Create systemd service ───
echo "▶ [6/6] Creating systemd service..."
USERNAME=$(whoami)
sudo tee /etc/systemd/system/ai-fashion-backend.service > /dev/null << SYSTEMD_EOF
[Unit]
Description=AI Fashion Designer Backend (uvicorn)
After=network.target

[Service]
Type=simple
User=$USERNAME
Group=$USERNAME
WorkingDirectory=$APP_DIR/app
Environment="PATH=$APP_DIR/app/venv/bin:/usr/bin"
ExecStart=$APP_DIR/app/venv/bin/uvicorn src.main:app \
    --host 127.0.0.1 \
    --port 8083 \
    --workers 2
Restart=always
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-fashion-backend

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ VM setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Create .env:  nano $APP_DIR/app/.env"
echo "  2. Setup Nginx:  bash scripts/nginx-setup.sh"
echo "  3. Start backend: sudo systemctl start ai-fashion-backend"
echo "  4. Upload images to: $APP_DIR/app/test_images/"
echo "═══════════════════════════════════════════════════════"
