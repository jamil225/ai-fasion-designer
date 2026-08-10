# GCP VM Deployment Guide — AI Fashion Designer

> **Last updated**: 2026-08-10
> **Phase**: 1 — Single VM, no Docker
> **Target project**: `peopleverdict-696f3` (account: `jmlahmdpp225@gmail.com`)

---

## Table of Contents

1. [Deployment Strategy & Decisions](#1-deployment-strategy--decisions)
2. [Prerequisites — Billing & API Enablement](#2-prerequisites--billing--api-enablement)
3. [VM Creation](#3-vm-creation)
4. [VM Initial Setup](#4-vm-initial-setup)
5. [Deploy Backend (FastAPI + uvicorn)](#5-deploy-backend-fastapi--uvicorn)
6. [Deploy Frontend (Vite React → Nginx)](#6-deploy-frontend-vite-react--nginx)
7. [Nginx Configuration (Reverse Proxy)](#7-nginx-configuration-reverse-proxy)
8. [Upload Images to the VM](#8-upload-images-to-the-vm)
9. [Environment Variables (.env)](#9-environment-variables-env)
10. [Start, Stop & Monitor](#10-start-stop--monitor)
11. [Firewall Rules](#11-firewall-rules)
12. [Verify the Deployment](#12-verify-the-deployment)
13. [Cost Awareness](#13-cost-awareness)
14. [Troubleshooting](#14-troubleshooting)
15. [Decision Log](#15-decision-log)
16. [Phase 2 Roadmap — Docker on Same VM](#16-phase-2-roadmap--docker-on-same-vm)

---

## 1. Deployment Strategy & Decisions

### What We're Deploying

```
┌─────────────────────────────────────────────────────────────────┐
│                    Single GCP VM (e2-small)                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                        Nginx                             │   │
│  │  :80 ──► static files (frontend/dist/)                   │   │
│  │  :80/v1/* ──► proxy_pass http://127.0.0.1:8083           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   uvicorn (systemd service)  :8083  ← backend            │   │
│  │   src.main:app                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  /srv/ai-fashion-designer/         ← app code (git clone)      │
│  /srv/ai-fashion-designer/images/  ← garment images            │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Architecture (Phase 1)

| Decision | Choice | Why |
|----------|--------|-----|
| **One VM** | `e2-small` (2 vCPU, 2 GB RAM) | Cheapest viable. FastAPI + Nginx fits comfortably. |
| **No Docker** | Bare systemd + Nginx | Fewer concepts at once. Learn Linux service management first. |
| **Nginx as reverse proxy** | Serves frontend static files + proxies `/v1/*` to uvicorn | Industry standard pattern. Single port 80 for everything. |
| **systemd** | uvicorn as a managed service | Auto-restart on crash, auto-start on boot, proper logging. |
| **OS** | Ubuntu 24.04 LTS (or Debian 12) | Best package ecosystem, widest documentation. |
| **Region** | `us-central1` | Matches your Vertex AI location. Cheapest tier. |

> **Learning note**: This is the exact same pattern used by most startups deploying Python web apps. Nginx handles HTTP traffic and static files efficiently (written in C, very fast). uvicorn handles your Python app. systemd is the Linux "service manager" that keeps your app running.

---

## 2. Prerequisites — Billing & API Enablement

### The Problem We Hit

Your GCP billing account (`017A5E-C7DA45-696B09` — "Google Cloud Platform Trial Billing Account") shows `OPEN: False`. This means:
- Either your free trial expired, or
- The billing account was disabled/suspended

GCP gives **$300 free credits** (may be $1,000 in some regions) valid for 90 days. **VMs are fully supported on trial credits** — there are no restrictions on Compute Engine during the trial.

### Fix: Re-enable Billing

1. **Open**: https://console.cloud.google.com/billing
2. If you see "Trial expired" or "Upgrade account":
   - Click **"Upgrade"** to convert to a pay-as-you-go account
   - You **won't be charged** until your credits run out AND you explicitly set a budget
   - Any remaining trial credits still apply
3. If the billing account is gone, **create a new one**:
   - Billing → **Create Account** → link a card → link to project `peopleverdict-696f3`
4. **Verify**: Go to project `peopleverdict-696f3` → **Billing** → should show "Billing is enabled"

### Enable Compute Engine API

After billing is active, enable the Compute Engine API:

```bash
# From your local terminal
gcloud services enable compute.googleapis.com --project=peopleverdict-696f3
```

Or via Console: **APIs & Services → Library → search "Compute Engine" → Enable**

> **Learning note**: GCP uses an API-per-service model. Even with billing active, each Google Cloud service (Compute Engine, Cloud Storage, etc.) must be explicitly enabled before use. This is a security/cost-control feature.

---

## 3. VM Creation

### Option A: Create via GCP Console (Recommended for Learning)

1. Go to: https://console.cloud.google.com/compute/instances?project=peopleverdict-696f3
2. Click **"Create Instance"**
3. Configure:

| Setting | Value | Why |
|---------|-------|-----|
| **Name** | `ai-fashion-designer` | Descriptive, lowercase with hyphens |
| **Region/Zone** | `us-central1-a` | Matches Vertex AI, cheap |
| **Machine type** | `e2-small` (2 vCPU, 2 GB) | ~$13/month. Sufficient for demo. |
| **Boot disk** | Ubuntu 24.04 LTS, 20 GB standard persistent disk | Default 10 GB is tight; 20 GB gives room for images + deps |
| **Firewall** | ✅ Allow HTTP traffic, ✅ Allow HTTPS traffic | Opens ports 80 and 443 |
| **Networking → External IP** | Ephemeral (default) | Gets a public IP. Fine for demo. |

4. Click **"Create"**

### Option B: Create via gcloud CLI

```bash
gcloud compute instances create ai-fashion-designer \
  --project=peopleverdict-696f3 \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --boot-disk-type=pd-standard \
  --tags=http-server,https-server \
  --metadata=enable-oslogin=true
```

### After Creation — Note Your External IP

```bash
gcloud compute instances describe ai-fashion-designer \
  --project=peopleverdict-696f3 \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Save this IP — you'll access the app at `http://<THIS_IP>/`.

> **Learning note**: The `--tags=http-server,https-server` automatically creates firewall rules allowing ingress on ports 80 and 443. GCP's default VPC has pre-built rules for these tags.

---

## 4. VM Initial Setup

SSH into the VM:

```bash
gcloud compute ssh ai-fashion-designer \
  --project=peopleverdict-696f3 \
  --zone=us-central1-a
```

Then run these setup commands on the VM:

```bash
# ─── 1. System update ───
sudo apt update && sudo apt upgrade -y

# ─── 2. Install Python 3.11+ ───
sudo apt install -y python3 python3-pip python3-venv git nginx

# Check version (should be 3.11 or 3.12)
python3 --version

# ─── 3. Install Node.js 20 LTS (for frontend build) ───
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version  # should be v20.x
npm --version

# ─── 4. Create app directory ───
sudo mkdir -p /srv/ai-fashion-designer
sudo chown $(whoami):$(whoami) /srv/ai-fashion-designer
```

> **Learning note**: `/srv/` is the standard Linux directory for "site-specific data served by this system." It's the conventional place for web application code on servers (vs `/home/` which is for user files, or `/opt/` for optional packages).

---

## 5. Deploy Backend (FastAPI + uvicorn)

### 5.1. Clone the Repository

```bash
cd /srv/ai-fashion-designer
git clone https://github.com/jamil225/ai-fasion-designer.git app
cd app

# Checkout the branch you want to deploy
git checkout feat/multi-provider-failover
```

### 5.2. Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5.3. Create the .env File

```bash
nano /srv/ai-fashion-designer/app/.env
```

Paste your environment variables (see [Section 9](#9-environment-variables-env) for the production version).

### 5.4. Create systemd Service

```bash
sudo nano /etc/systemd/system/ai-fashion-backend.service
```

Paste this content:

```ini
[Unit]
Description=AI Fashion Designer Backend (uvicorn)
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/srv/ai-fashion-designer/app
Environment="PATH=/srv/ai-fashion-designer/app/venv/bin:/usr/bin"
ExecStart=/srv/ai-fashion-designer/app/venv/bin/uvicorn src.main:app \
    --host 127.0.0.1 \
    --port 8083 \
    --workers 2
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/srv/ai-fashion-designer

[Install]
WantedBy=multi-user.target
```

> **Replace** `YOUR_USERNAME` with the output of `whoami` on the VM.

### 5.5. Start the Backend Service

```bash
# Reload systemd to pick up the new service file
sudo systemctl daemon-reload

# Enable (auto-start on boot) and start
sudo systemctl enable ai-fashion-backend
sudo systemctl start ai-fashion-backend

# Check status
sudo systemctl status ai-fashion-backend

# View logs (live tail)
journalctl -u ai-fashion-backend -f
```

> **Learning note — systemd explained**:
> - `systemctl enable` = "start this service automatically when the VM boots"
> - `systemctl start` = "start it right now"
> - `Restart=always` = "if the process crashes, restart it after 5 seconds"
> - `--host 127.0.0.1` = only listen on localhost (Nginx will proxy external traffic to it)
> - `--workers 2` = 2 uvicorn workers handle requests. Enough for demo traffic.

---

## 6. Deploy Frontend (Vite React → Nginx)

### 6.1. Build the Frontend on the VM

```bash
cd /srv/ai-fashion-designer/app/frontend

# Create production .env for Vite build
cat > .env.production << 'EOF'
VITE_GOOGLE_CLIENT_ID=50507686337-cgbkqmro01n4boolifghfkl21p6lbgtl.apps.googleusercontent.com
EOF

npm install
npm run build
```

This produces the `dist/` directory with static HTML/CSS/JS files.

### 6.2. Copy Build to Nginx Serving Directory

```bash
sudo mkdir -p /var/www/ai-fashion-designer
sudo cp -r /srv/ai-fashion-designer/app/frontend/dist/* /var/www/ai-fashion-designer/
```

> **Learning note**: Nginx serves static files from `/var/www/` by convention. The `dist/` folder from Vite contains the fully built, optimized frontend — just HTML, CSS, and JS. No Node.js server needed in production.

---

## 7. Nginx Configuration (Reverse Proxy)

### 7.1. Create Nginx Site Config

```bash
sudo nano /etc/nginx/sites-available/ai-fashion-designer
```

Paste:

```nginx
server {
    listen 80;
    server_name _;  # Responds to any hostname (IP-based access)

    # ─── Frontend: serve static files ───
    root /var/www/ai-fashion-designer;
    index index.html;

    # ─── API: reverse proxy /v1/* to uvicorn ───
    location /v1/ {
        proxy_pass http://127.0.0.1:8083;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase timeouts for ingestion (can take minutes)
        proxy_read_timeout 600s;
        proxy_connect_timeout 10s;
    }

    # ─── SPA fallback: serve index.html for client-side routes ───
    location / {
        try_files $uri $uri/ /index.html;
    }

    # ─── Security headers ───
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # ─── Gzip compression ───
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1000;
}
```

### 7.2. Enable the Site

```bash
# Remove default Nginx site
sudo rm /etc/nginx/sites-enabled/default

# Enable our site
sudo ln -s /etc/nginx/sites-available/ai-fashion-designer /etc/nginx/sites-enabled/

# Test config syntax
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

> **Learning note — How Nginx Reverse Proxy Works**:
>
> ```
> Browser → http://VM_IP/                → Nginx → serves index.html (frontend)
> Browser → http://VM_IP/v1/health       → Nginx → proxy_pass → uvicorn:8083 → FastAPI
> Browser → http://VM_IP/v1/search       → Nginx → proxy_pass → uvicorn:8083 → FastAPI
> Browser → http://VM_IP/assets/main.js  → Nginx → serves static JS file
> ```
>
> Nginx acts as a **traffic router**. It's extremely fast at serving static files (much faster than Python). For API calls (`/v1/*`), it forwards the request to your Python backend running on `localhost:8083`. The backend never talks directly to the internet — Nginx is the single entry point.

---

## 8. Upload Images to the VM

### Option A: SCP from Local Machine

```bash
# From your local machine (not the VM)
gcloud compute scp --recurse \
  /Users/dev/ai-fasion-designer/test_images/* \
  ai-fashion-designer:/srv/ai-fashion-designer/app/test_images/ \
  --project=peopleverdict-696f3 \
  --zone=us-central1-a
```

### Option B: Upload via GCP Console

1. SSH into the VM via the GCP Console (click "SSH" button on the VM instances page)
2. Use the gear icon → "Upload file" in the SSH window
3. Move uploaded files to the image directory

### Option C: Download Directly on VM (if images are online)

```bash
# If you have images in a GCS bucket or public URL
gsutil cp -r gs://your-bucket/images/* /srv/ai-fashion-designer/app/test_images/
```

---

## 9. Environment Variables (.env)

Create the production `.env` on the VM. **Key differences from local**:

```bash
# External API Keys
OPENAI_API_KEY=sk-proj-...your-key...
PINECONE_API_KEY=pcsk_...your-key...

# Pinecone Settings
PINECONE_INDEX_NAME=fashion-designer-rag
PINECONE_ENVIRONMENT=us-east-1

# Application Settings
APP_API_KEY=<GENERATE_A_STRONG_KEY>
IMAGE_FOLDER_PATH=/srv/ai-fashion-designer/app/test_images
DEFAULT_TOP_K=10
HQ_IMAGE_FOLDER_PATH=/srv/ai-fashion-designer/app/hq_images

# Vertex AI (VM uses ADC — Application Default Credentials)
GOOGLE_CLOUD_PROJECT=peopleverdict-696f3
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
VISION_MODEL_NAME=gemini-2.5-flash-lite
MERGE_MODEL_NAME=gemini-2.5-flash-lite

# Google OAuth
GOOGLE_CLIENT_ID=50507686337-cgbkqmro01n4boolifghfkl21p6lbgtl.apps.googleusercontent.com
SESSION_SECRET=<GENERATE_A_STRONG_SECRET>

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...your-key...
LANGCHAIN_PROJECT=ai-fashion-designer-prod

# LLM gateway
LLM_BACKEND=vertex
LLM_FALLBACK_ENABLED=false
```

### Important Production Differences

| Setting | Local | Production (VM) | Why |
|---------|-------|-----------------|-----|
| `IMAGE_FOLDER_PATH` | `/Users/dev/.../test_images` | `/srv/ai-fashion-designer/app/test_images` | Different filesystem |
| `APP_API_KEY` | `test-key-123` | Strong random key | Security |
| `SESSION_SECRET` | Dev value | New random value | Security |
| `LLM_FALLBACK_ENABLED` | `true` | `false` (initially) | Avoid OpenAI costs |

### Generate Strong Keys

```bash
# Run this on the VM to generate random keys
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Vertex AI ADC on GCE

When running on a GCE VM within project `peopleverdict-696f3`, **Application Default Credentials (ADC) work automatically** — no service account key file needed. The VM's default service account has access to Vertex AI APIs.

> **Learning note**: On your Mac you had to run `gcloud auth application-default login` to get ADC. On a GCE VM, ADC comes pre-configured via the VM's metadata server. This is the recommended production pattern — no key files to manage.

Make sure the Vertex AI API is enabled:

```bash
gcloud services enable aiplatform.googleapis.com --project=peopleverdict-696f3
```

---

## 10. Start, Stop & Monitor

### Service Management

```bash
# Start / stop / restart backend
sudo systemctl start ai-fashion-backend
sudo systemctl stop ai-fashion-backend
sudo systemctl restart ai-fashion-backend

# Check status
sudo systemctl status ai-fashion-backend

# View backend logs (live)
journalctl -u ai-fashion-backend -f

# View last 50 lines of backend logs
journalctl -u ai-fashion-backend -n 50

# Nginx status and logs
sudo systemctl status nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### After Code Updates

```bash
cd /srv/ai-fashion-designer/app
git pull

# Backend update
source venv/bin/activate
pip install -r requirements.txt  # only if deps changed
sudo systemctl restart ai-fashion-backend

# Frontend update
cd frontend
npm install  # only if deps changed
npm run build
sudo cp -r dist/* /var/www/ai-fashion-designer/
```

---

## 11. Firewall Rules

The VM tags `http-server` and `https-server` auto-create these rules:

| Rule | Protocol | Port | Source | Purpose |
|------|----------|------|--------|---------|
| `default-allow-http` | TCP | 80 | 0.0.0.0/0 | HTTP access |
| `default-allow-https` | TCP | 443 | 0.0.0.0/0 | HTTPS access (future) |

Port 8083 (uvicorn) is **NOT** exposed externally — it only listens on `127.0.0.1`. All external traffic goes through Nginx on port 80.

> **Learning note**: This is a security best practice called "defense in depth." Even if someone discovers your backend port, they can't reach it directly from the internet. Only Nginx (running on the same machine) can talk to uvicorn.

---

## 12. Verify the Deployment

Once everything is running, test:

```bash
# From the VM itself
curl http://localhost:8083/v1/health    # Backend directly
curl http://localhost/v1/health          # Through Nginx
curl http://localhost/                   # Frontend

# From your local machine (replace with your VM's external IP)
curl http://<VM_EXTERNAL_IP>/v1/health
```

Then open in your browser:
- `http://<VM_EXTERNAL_IP>/` → should show the login page
- `http://<VM_EXTERNAL_IP>/v1/health` → should return `{"status":"healthy",...}`

### Google OAuth — Add Authorized Origin

For Google Login to work on the VM, you must add the VM's IP to your OAuth consent screen:

1. Go to: https://console.cloud.google.com/apis/credentials
2. Find your OAuth 2.0 Client ID (`50507686337-cgb...`)
3. Under **Authorized JavaScript origins**, add: `http://<VM_EXTERNAL_IP>`
4. Under **Authorized redirect URIs**, add: `http://<VM_EXTERNAL_IP>`
5. Save

> **Learning note**: Google OAuth only works from domains/IPs you've explicitly whitelisted. This prevents attackers from using your client ID on their own site.

---

## 13. Cost Awareness

### Estimated Monthly Cost (e2-small, us-central1)

| Resource | Cost/month | Notes |
|----------|-----------|-------|
| e2-small VM (sustained use) | ~$13.00 | 2 vCPU, 2 GB RAM |
| 20 GB standard persistent disk | ~$0.80 | Standard PD |
| Network egress | ~$0.00 | Free tier covers demo traffic |
| **Total** | **~$14/month** | Covered by trial credits |

### Cost-Saving Tips

- **Stop the VM** when not in use: `gcloud compute instances stop ai-fashion-designer --zone=us-central1-a --project=peopleverdict-696f3` — stopped VMs only pay for disk (~$0.80/month)
- **Start again**: `gcloud compute instances start ai-fashion-designer --zone=us-central1-a --project=peopleverdict-696f3`
- Your IP will change when you stop/start (ephemeral IP). If this bothers you, reserve a static IP ($0/month while attached to a running VM, ~$2.88/month if unattached).

> **Learning note**: The biggest cost trap in cloud is forgetting to shut down resources. **Set a billing alert**: Console → Billing → Budgets & Alerts → create a $50 alert. This sends you an email before you accidentally burn credits.

---

## 14. Troubleshooting

### Backend won't start

```bash
# Check logs
journalctl -u ai-fashion-backend -n 100 --no-pager

# Common issues:
# 1. Missing .env file → check path in WorkingDirectory
# 2. Wrong Python path → verify venv/bin/uvicorn exists
# 3. Port already in use → sudo lsof -i :8083
# 4. Permission denied → check User/Group in service file
```

### Nginx returns 502 Bad Gateway

```bash
# Backend is not running or not on port 8083
sudo systemctl status ai-fashion-backend
curl http://127.0.0.1:8083/v1/health  # test backend directly
```

### Can't reach the VM externally

```bash
# Check firewall rules
gcloud compute firewall-rules list --project=peopleverdict-696f3

# Check if Nginx is listening on port 80
sudo ss -tlnp | grep :80
```

### Vertex AI / Gemini errors

```bash
# Check that the API is enabled
gcloud services list --enabled --project=peopleverdict-696f3 | grep aiplatform

# Check VM's service account has permissions
gcloud compute instances describe ai-fashion-designer \
  --zone=us-central1-a \
  --project=peopleverdict-696f3 \
  --format='get(serviceAccounts[0].email)'

# That service account should have "Vertex AI User" role
```

---

## 15. Decision Log

| # | Decision | Choice | Alternatives | Rationale |
|---|----------|--------|-------------|-----------|
| D1 | Deployment target | Single GCE VM | Cloud Run, GKE, App Engine | Simplest to learn. Full control. Cheapest for always-on demo. |
| D2 | VM size | `e2-small` (2 vCPU, 2 GB) | `e2-micro` (shared), `e2-medium` | Micro might OOM during ingestion. Small is $13/mo — affordable on trial credits. |
| D3 | OS | Ubuntu 24.04 LTS | Debian 12, Container-Optimized OS | Widest docs, latest packages, LTS support until 2029. |
| D4 | Frontend serving | Nginx static files | uvicorn serving, separate VM | Nginx is 10x faster at static files. Single VM keeps it simple. |
| D5 | Backend process manager | systemd | supervisor, pm2 | systemd is built into every modern Linux. No extra install. |
| D6 | Backend exposure | localhost only (127.0.0.1) | 0.0.0.0 (public) | Security: Nginx is the only public entry point. |
| D7 | Container strategy | Phase 1: none, Phase 2: Docker | Docker from day 1 | Isolate learning — GCP/Linux fundamentals first, then Docker. |
| D8 | Auth on VM | ADC (automatic) | Service account key file | GCE VMs get ADC from metadata server. No key files to manage. |
| D9 | IP address | Ephemeral | Static IP | Free. Acceptable for demo. Static IP is easy to add later. |
| D10 | SSL/HTTPS | Deferred | Certbot/Let's Encrypt | Needs a domain name. IP-based access works for now. |
| D11 | Disk size | 20 GB standard | 10 GB (default), SSD | 10 GB is tight after OS + Python deps + images. SSD is overkill. |
| D12 | Region | us-central1 | Other regions | Matches Vertex AI location. Cheapest e2 pricing. |
| D13 | Account for deployment | jmlin786@gmail.com + peopleverdict-696f3 | jamil.ahmad7720@gmail.com | Keep Vertex AI project consistent with existing config. |
| D14 | Trial credits | Yes, fully supported | Need paid account | GCE is available on trial. $1,000 credits = ~71 months of e2-small. |

---

## 16. Phase 2 Roadmap — Docker on Same VM

Once Phase 1 is stable and you're comfortable with the VM:

1. Install Docker on the VM
2. Create a `Dockerfile` for the backend (Python + uvicorn)
3. Create a `Dockerfile` for the frontend (multi-stage: Node build → Nginx serve)
4. Create `docker-compose.yml` connecting both services
5. Replace systemd service with `docker compose up -d`
6. Nginx config moves inside the frontend container

**Why Docker later?**
- Same containers run unchanged on Cloud Run / GKE if you outgrow one VM
- Reproducible builds — `docker build` produces identical images everywhere
- Easy rollbacks — just point to a previous image tag
- But it's an entire new layer of concepts (images, layers, networks, volumes) — better to learn it as an isolated step

---

## Quick Reference — Common Commands

```bash
# SSH into the VM
gcloud compute ssh ai-fashion-designer --project=peopleverdict-696f3 --zone=us-central1-a

# Start/stop the VM itself
gcloud compute instances start ai-fashion-designer --zone=us-central1-a --project=peopleverdict-696f3
gcloud compute instances stop ai-fashion-designer --zone=us-central1-a --project=peopleverdict-696f3

# Backend service
sudo systemctl restart ai-fashion-backend
journalctl -u ai-fashion-backend -f

# Nginx
sudo systemctl reload nginx
sudo nginx -t

# Upload files to VM
gcloud compute scp LOCAL_FILE ai-fashion-designer:REMOTE_PATH --zone=us-central1-a --project=peopleverdict-696f3

# Get VM external IP
gcloud compute instances describe ai-fashion-designer --zone=us-central1-a --project=peopleverdict-696f3 --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```
