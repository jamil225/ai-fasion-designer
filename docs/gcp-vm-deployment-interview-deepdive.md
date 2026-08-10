# GCP VM Deployment — Deep-Dive Interview Preparation & Concept Guide

> **Project**: `peopleverdict-696f3`  
> **Instance**: `ai-fashion-designer` (Zone: `asia-south1-a`, Mumbai)  
> **Domain**: `https://8.234.93.21.nip.io/`  
> **Target Audience**: Cloud / AI Software Engineer Interviews

---

## Executive Summary

This document distills the complete GCP Compute Engine deployment of the AI Fashion Designer application into a structured, interview-ready format. It covers every deployment step in sequence, why each choice was made, the technical root causes of real-world bugs encountered, and senior-level interview Q&A patterns.

---

## Part 1: Chronological Deployment Sequence (What, Why, and Learnings)

### Step 1: Trial Billing & Project Setup
- **What Was Done**: Activated a fresh GCP account (`jmlahmdpp225@gmail.com`) with project `peopleverdict-696f3` to leverage $300 90-day free trial credits.
- **Why**: The original project's trial billing account (`017A5E-C7DA45-696B09`) was closed (`OPEN: False`), causing API enablement calls (`compute.googleapis.com`) to fail with billing errors.
- **Interview Concept**: *"GCP Compute Engine VMs are fully supported by free trial credits. When trial accounts expire, APIs throw billing-disabled exceptions. Creating a fresh project or linking a valid billing account with budget alerts is standard procedure."*

---

### Step 2: GCE Instance Provisioning & Regional Capacity Management
- **What Was Done**: Provisioned an `e2-small` VM (2 vCPU, 2 GB RAM, 20 GB standard persistent disk, Ubuntu 24.04 LTS) in `asia-south1-a` (Mumbai).
- **Why**: Initial provisioning in default zone `us-central1-a` failed with `ZONE_RESOURCE_POOL_EXHAUSTED` due to high demand for free-tier/small machine types.
- **Interview Concept**: *"Resource pool exhaustion is common in high-traffic default zones. Switching to an alternate zone in the same or nearby region resolves capacity blocks. Vertex AI backend calls remain regionalized (`us-central1` in `.env`) regardless of where the compute instance resides."*

---

### Step 3: VPC Ingress Firewall Rules Configuration
- **What Was Done**: Created explicit VPC ingress firewall rules `allow-http` (port 80) and `allow-https` (port 443) targeting network tags `http-server` and `https-server`.
- **Why**: Passing `--tags=http-server` to a VM attaches network tags, but **new GCP VPC networks omit public web ingress firewall rules by default**, leading to `ERR_CONNECTION_TIMED_OUT`.
- **Interview Concept**: *"VM network tags are metadata markers; they only grant access if corresponding VPC ingress firewall rules exist specifying allowed protocols, ports (80/443), and source IP ranges (`0.0.0.0/0`)."*

---

### Step 4: Environment Provisioning & Vite Build-Time Env Embedding
- **What Was Done**: Installed system packages (`python3-venv`, `git`, `nginx`, `nodejs 20`), created python venv, installed requirements, created `frontend/.env` containing `VITE_GOOGLE_CLIENT_ID`, and ran `npm run build`.
- **Why**: Vite embeds `VITE_` variables directly into static JavaScript assets at build time (`npm run build`). If `frontend/.env` is missing during build, environment tokens compile as `undefined`.
- **Interview Concept**: *"Client-side SPA frameworks (Vite/React) static-inline environment variables during build time. Updating frontend environment variables on a server requires regenerating static assets with `npm run build` and recopying `dist/` to Nginx."*

---

### Step 5: systemd Process Supervision
- **What Was Done**: Configured `/etc/systemd/system/ai-fashion-backend.service` running `uvicorn src.main:app --host 127.0.0.1 --port 8083` with `Restart=always`.
- **Why**: `systemd` acts as an OS-level supervisor ensuring automatic start on VM boot, crash auto-recovery, and clean log routing via `journalctl`.
- **Interview Concept**: *"Binding Uvicorn to `127.0.0.1` keeps the Python backend private. Only Nginx (running on the same host) can talk to Uvicorn, implementing defense-in-depth."*

---

### Step 6: Nginx Reverse Proxy & `nip.io` Wildcard DNS Setup
- **What Was Done**: Configured Nginx to serve static files from `/var/www/ai-fashion-designer` and `proxy_pass http://127.0.0.1:8083` for `/v1/*`. Used domain `8.234.93.21.nip.io`.
- **Why**: Google OAuth 2.0 security policy forbids raw IP addresses in Authorized JavaScript Origins. `nip.io` acts as a wildcard DNS mapping `8.234.93.21.nip.io` directly to IP `8.234.93.21`, satisfying Google's TLD validation without buying a domain.
- **Interview Concept**: *"Nginx acts as a high-performance reverse proxy (C-based static file serving, connection buffering, SSL termination). `nip.io` provides instant TLD compliance for staging/demo environments."*

---

### Step 7: Let's Encrypt SSL via Certbot
- **What Was Done**: Set `server_name 8.234.93.21.nip.io;` in Nginx and executed `sudo certbot --nginx -d 8.234.93.21.nip.io`.
- **Why**: Google OAuth Consent Screens in "In Production" status reject `http://` origins for non-localhost domains, requiring valid HTTPS.
- **Interview Concept**: *"Certbot automates Let's Encrypt SSL certificate issuance and Nginx HTTPS block configuration, enabling production-compliant OAuth over HTTPS."*

---

### Step 8: GCE Service Account Scopes Fix (`cloud-platform`)
- **What Was Done**: Stopped VM, updated scopes with `gcloud compute instances set-service-account --scopes=cloud-platform`, and restarted.
- **Why**: Default GCE instances are created with restricted OAuth access scopes. Calling Vertex AI via Application Default Credentials (ADC) threw `403 PERMISSION_DENIED: ACCESS_TOKEN_SCOPE_INSUFFICIENT`.
- **Interview Concept**: *"IAM roles and GCE access scopes work together. A service account with full IAM roles will still be blocked if the VM instance's OAuth access scope omits `cloud-platform`."*

---

## Part 2: Top Technical Interview Questions & Senior Responses

### Q1: Why use Nginx as a reverse proxy in front of Uvicorn instead of exposing Uvicorn directly to the internet?
> **Response**:  
> "Uvicorn is an ASGI application server optimized for running async Python code, but it is not designed to be a public-facing web server. Nginx sits in front as a reverse proxy for three reasons:
> 1. **Performance & Static File Delivery**: Nginx is written in C and handles static assets (HTML/CSS/JS) with minimal memory overhead, saving Python worker threads for dynamic business logic.
> 2. **Security & Attack Surface Reduction**: Uvicorn binds to `127.0.0.1:8083` (localhost only). Nginx handles public internet traffic on ports 80/443, mitigating slowloris attacks, buffering slow clients, and managing SSL termination.
> 3. **Routing Flexibility**: Nginx seamlessly routes `/` to static frontend files and `/v1/*` to the FastAPI backend under a single unified origin, avoiding CORS issues."

---

### Q2: How does Application Default Credentials (ADC) work on a Google Compute Engine VM without service account key files?
> **Response**:  
> "On Google Compute Engine, Google SDKs (like `google-genai` or `google-cloud-aiplatform`) automatically discover credentials via the internal Metadata Server running at `http://metadata.google.internal/` (or `169.254.169.254`).  
> When the code initializes a Vertex AI client, the SDK queries the local metadata server for a short-lived OAuth access token associated with the VM's attached service account. This eliminates storing sensitive service account JSON key files on disk."

---

### Q3: What is the difference between GCP IAM Roles and GCE Instance Access Scopes?
> **Response**:  
> "Both act as authorization gates, and **both must allow the action** for a request to succeed:
> - **IAM Roles** grant permissions to the *identity* (the Service Account).
> - **Access Scopes** set the maximum permission ceiling for the *instance itself*.
> If a Service Account has the `Vertex AI Administrator` IAM role, but the GCE instance was provisioned with default scopes (which exclude `cloud-platform`), requests to Vertex AI will fail with `403 ACCESS_TOKEN_SCOPE_INSUFFICIENT`. Setting `--scopes=cloud-platform` delegates full authorization control to IAM."

---

### Q4: Why did Google OAuth reject raw IP addresses, and how does wildcard DNS (`nip.io`) resolve it?
> **Response**:  
> "Google OAuth 2.0 validation policies require Authorized JavaScript Origins to be either `localhost` or end in a valid public Top-Level Domain (TLD) like `.com` or `.io`. Raw IP addresses like `http://8.234.93.21` are rejected to prevent phishing and enforce domain ownership.  
> `nip.io` is a wildcard DNS service that dynamically resolves any hostname in the format `<IP>.nip.io` back to `<IP>`. Because `8.234.93.21.nip.io` ends in `.io`, it satisfies Google's TLD validation while routing directly to our VM's IP address."

---

### Q5: How do you manage application lifecycle and crash recovery on a single VM without Docker?
> **Response**:  
> "We use **systemd**, the native Linux init system and service manager. We define a unit file at `/etc/systemd/system/ai-fashion-backend.service` specifying `ExecStart`, `WorkingDirectory`, and environment variables.  
> We set `Restart=always` and `RestartSec=5` so that if Uvicorn crashes due to an unhandled exception or out-of-memory event, systemd automatically restarts the process within 5 seconds. Logging is routed to `journalctl`, allowing live inspection with `journalctl -u ai-fashion-backend -f`."
