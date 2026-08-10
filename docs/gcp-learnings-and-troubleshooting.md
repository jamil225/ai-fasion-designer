# GCP Deployment Learnings & Troubleshooting Log — AI Fashion Designer

> **Project**: `peopleverdict-696f3`  
> **VM Instance**: `ai-fashion-designer` (Zone: `asia-south1-a`)  
> **Domain**: `https://8.234.93.21.nip.io/`  
> **Date**: 2026-08-10

---

## Executive Summary

This document captures all technical roadblocks, architecture decisions, root-cause analyses, and concrete fixes established during the deployment of the AI Fashion Designer application onto Google Cloud Platform (GCP Compute Engine + Nginx + FastAPI + Vertex AI).

---

## 1. Issue: Closed GCP Trial Billing Account

### Problem
Attempting to enable GCP APIs (`compute.googleapis.com`) or create VM instances returned:
```
ERROR: Billing account for project '350306117860' is not open. Billing must be enabled for activation of service(s) to proceed.
```

### Root Cause
The original trial billing account (`017A5E-C7DA45-696B09`) had expired or reached closed status (`OPEN: False`), preventing Compute Engine resource allocation.

### Fix & Learning
1. GCP **free trial credits ($300 for 90 days) fully support Compute Engine VM deployment**.
2. Created a fresh Google account (`jmlahmdpp225@gmail.com`) with a new GCP project (`peopleverdict-696f3`).
3. Activated $300 trial credits, enabling seamless GCE deployment without admin approval overhead.

---

## 2. Issue: `ZONE_RESOURCE_POOL_EXHAUSTED` in Default Zone

### Problem
Running `gcloud compute instances create` in `us-central1-a` failed with:
```
ERROR: (gcloud.compute.instances.create) Could not fetch resource: ZONE_RESOURCE_POOL_EXHAUSTED
A e2-small VM instance is currently unavailable in the us-central1-a zone.
```

### Root Cause
`us-central1-a` is a high-demand default zone where small VM types (`e2-small`) frequently experience temporary capacity shortages.

### Fix & Learning
- Switched target deployment zone to **`asia-south1-a`** (Mumbai, India).
- **Learning**: Vertex AI calls (configured for `us-central1` in `.env`) work seamlessly regardless of where the GCE VM is physically located. Deploying the VM in Mumbai also improved UI responsiveness for local testing.

---

## 3. Issue: `ERR_CONNECTION_TIMED_OUT` (Missing GCP Firewall Rules)

### Problem
Navigating to `http://8.234.93.21/` resulted in `8.234.93.21 took too long to respond` (`ERR_CONNECTION_TIMED_OUT`).

### Root Cause
Passing `--tags=http-server,https-server` during VM creation attaches network tags to the VM, but **new GCP projects do not automatically contain default ingress firewall rules** for port 80 or 443. `gcloud compute firewall-rules list` confirmed only SSH (22) and ICMP were allowed.

### Fix & Learning
Created explicit VPC ingress firewall rules for ports 80 and 443:
```bash
gcloud compute firewall-rules create allow-http \
  --project=peopleverdict-696f3 \
  --direction=INGRESS --priority=1000 \
  --network=default --action=ALLOW --rules=tcp:80 \
  --target-tags=http-server

gcloud compute firewall-rules create allow-https \
  --project=peopleverdict-696f3 \
  --direction=INGRESS --priority=1000 \
  --network=default --action=ALLOW --rules=tcp:443 \
  --target-tags=https-server
```

---

## 4. Issue: `⚠️ Google Client ID not configured` in Frontend

### Problem
After opening the app in browser, the sign-in page displayed:
```
⚠️ Google Client ID not configured. Set VITE_GOOGLE_CLIENT_ID in frontend/.env
```

### Root Cause
Vite is a client-side bundler. Environment variables starting with `VITE_` are **baked directly into static JS bundles at build time (`npm run build`)**. If `frontend/.env` is missing during build, the variable resolves to `undefined` in compiled JS.

### Fix & Learning
1. Created `frontend/.env` on the VM before running `npm run build`:
   ```bash
   echo "VITE_GOOGLE_CLIENT_ID=YOUR_CLIENT_ID" > /srv/ai-fashion-designer/app/frontend/.env
   ```
2. Rebuilt static assets (`npm run build`) and copied output to `/var/www/ai-fashion-designer/`.

---

## 5. Issue: Google OAuth Rejection of Raw IP (`Invalid Origin`)

### Problem
Entering `http://8.234.93.21` into Google Cloud Console Authorized Origins returned:
```
Invalid Origin: must end with a public top-level domain (such as .com or .org).
```

### Root Cause
Google OAuth 2.0 security policy strictly prohibits raw IP addresses in Authorized JavaScript Origins (allowing only `localhost` or valid top-level domain names).

### Fix & Learning
- Used **`nip.io`** (free wildcard DNS service). `8.234.93.21.nip.io` maps directly to IP `8.234.93.21`.
- Entered `http://8.234.93.21.nip.io` into Google Console, which satisfied Google's TLD validator (`.io`).

---

## 6. Issue: OAuth "In Production" HTTPS Requirement

### Problem
Saving `http://8.234.93.21.nip.io` in Google Console failed with:
```
Invalid Origin: This app has a publishing status of "In production". URI must use https:// as the scheme.
```

### Root Cause
OAuth consent screens with `Publishing status: In production` force all non-localhost origins to use `https://`.

### Fix & Learning
1. Updated Nginx site configuration on VM with explicit domain:
   ```nginx
   server_name 8.234.93.21.nip.io;
   ```
2. Installed Let's Encrypt SSL certificate via Certbot:
   ```bash
   sudo certbot --nginx -d 8.234.93.21.nip.io
   ```
3. Secured site under `https://8.234.93.21.nip.io/` with valid SSL certificate, satisfying Google OAuth production rules.

---

## 7. Issue: Vertex AI 403 `ACCESS_TOKEN_SCOPE_INSUFFICIENT`

### Problem
Backend POST `/v1/chat` returned HTTP 500. Backend logs (`journalctl`) revealed:
```
langchain_google_genai.chat_models.ChatGoogleGenerativeAIError: Error calling model 'gemini-2.5-pro' (PERMISSION_DENIED): 403 PERMISSION_DENIED.
Reason: ACCESS_TOKEN_SCOPE_INSUFFICIENT (service: aiplatform.googleapis.com)
```

### Root Cause
GCE VMs are created by default with restricted service account OAuth access scopes. Even though Application Default Credentials (ADC) are active, the VM instance lacked the `https://www.googleapis.com/auth/cloud-platform` scope needed to call Vertex AI Prediction API.

### Fix & Learning
Updated GCE instance service account scope:
```bash
# 1. Stop VM
gcloud compute instances stop ai-fashion-designer --zone=asia-south1-a --project=peopleverdict-696f3

# 2. Set full cloud-platform access scope
gcloud compute instances set-service-account ai-fashion-designer \
  --zone=asia-south1-a --project=peopleverdict-696f3 \
  --scopes=cloud-platform

# 3. Start VM
gcloud compute instances start ai-fashion-designer --zone=asia-south1-a --project=peopleverdict-696f3
```
After scope update, Vertex AI calls via ADC succeeded with 200 OK.

---

## Architecture Summary (Final Production Topology)

```
Browser (HTTPS)
  │
  ▼
https://8.234.93.21.nip.io/ (Port 443)
  │
  ▼
Nginx (Reverse Proxy & Static Web Server)
  ├── Serves static React frontend from /var/www/ai-fashion-designer/
  └── Proxies /v1/* requests ──► http://127.0.0.1:8083 (localhost only)
                                      │
                                      ▼
                             FastAPI + Uvicorn
                         (systemd service: ai-fashion-backend)
                                      │
                                      ├── Google Vertex AI (Gemini 2.5 Pro via ADC)
                                      ├── OpenAI (text-embedding-3-small)
                                      └── Pinecone Vector Database
```
