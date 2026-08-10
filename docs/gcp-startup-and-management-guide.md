# GCP Operations & Startup Guide — AI Fashion Designer

> **Project**: `peopleverdict-696f3`  
> **VM Instance**: `ai-fashion-designer` (Zone: `asia-south1-a`)  
> **Live Domain**: `https://8.234.93.21.nip.io/`  
> **Updated**: 2026-08-10

---

## Table of Contents

1. [Daily Startup Sequence (Resuming Work)](#1-daily-startup-sequence-resuming-work)
2. [Clean Shutdown Sequence (Saving Credits)](#2-clean-shutdown-sequence-saving-credits)
3. [Live Logging & Monitoring](#3-live-logging--monitoring)
4. [Updating Code & Rebuilding](#4-updating-code--rebuilding)
5. [Complete Sequenced Command Cheatsheet (Line-by-Line Comments)](#5-complete-sequenced-command-cheatsheet-line-by-line-comments)

---

## 1. Daily Startup Sequence (Resuming Work)

When you come back to work on the app after stopping the VM, follow this 3-step sequence:

### Step 1: Start the VM Instance (Local Mac Terminal)
```bash
# Start the VM instance in GCP
gcloud compute instances start ai-fashion-designer \
  --project=peopleverdict-696f3 \
  --zone=asia-south1-a
```

### Step 2: SSH into the VM (Local Mac Terminal)
```bash
# SSH into your VM terminal
gcloud compute ssh ai-fashion-designer \
  --project=peopleverdict-696f3 \
  --zone=asia-south1-a
```

### Step 3: Verify Services & View Live Logs (Inside VM SSH Session)
```bash
# Check FastAPI backend service status
sudo systemctl status ai-fashion-backend

# Check Nginx web server status
sudo systemctl status nginx

# View live streaming application logs (Press Ctrl+C to exit without stopping)
sudo journalctl -u ai-fashion-backend -f
```

---

## 2. Clean Shutdown Sequence (Saving Credits)

When you are done testing or working for the day, stop the VM to pause compute charges (~$13/month). When stopped, you only pay ~$0.80/month for disk storage.

### Step 1: Stop Services (Inside VM SSH Session - Optional)
```bash
# Gracefully stop the FastAPI backend service
sudo systemctl stop ai-fashion-backend

# Stop Nginx web server
sudo systemctl stop nginx

# Exit SSH session
exit
```

### Step 2: Stop the VM Instance (Local Mac Terminal - Required)
```bash
# Stop the VM instance in GCP to pause compute billing
gcloud compute instances stop ai-fashion-designer \
  --project=peopleverdict-696f3 \
  --zone=asia-south1-a
```

### Step 3: Verify VM Status (Local Mac Terminal)
```bash
# Confirm status is TERMINATED (not RUNNING)
gcloud compute instances list --project=peopleverdict-696f3
```

---

## 3. Live Logging & Monitoring

| Purpose | Command | Notes |
|---|---|---|
| **Stream Live Backend Logs** | `sudo journalctl -u ai-fashion-backend -f` | Shows real-time request logs & LLM calls. Press `q` or `Ctrl+C` to exit. |
| **View Last 50 Log Lines** | `sudo journalctl -u ai-fashion-backend -n 50 --no-pager` | Prints last 50 lines and immediately returns to command prompt. |
| **Check Nginx Access Logs** | `sudo tail -f /var/log/nginx/access.log` | Shows incoming HTTP/HTTPS web requests. |
| **Check Nginx Error Logs** | `sudo tail -f /var/log/nginx/error.log` | Shows web server proxying errors. |
| **Check Backend Status** | `sudo systemctl status ai-fashion-backend` | Shows systemd service state (Press `q` to exit). |

---

## 4. Updating Code & Rebuilding

Whenever you push new code changes to GitHub and want to update the VM:

```bash
# 1. SSH into VM
gcloud compute ssh ai-fashion-designer --project=peopleverdict-696f3 --zone=asia-south1-a

# 2. Pull latest code from repository
cd /srv/ai-fashion-designer/app
git pull

# 3. Update Python dependencies (if requirements.txt changed)
source venv/bin/activate
pip install -r requirements.txt

# 4. Rebuild React frontend
cd frontend
npm install
npm run build
sudo cp -r dist/* /var/www/ai-fashion-designer/

# 5. Restart backend service
sudo systemctl restart ai-fashion-backend
```

---

## 5. Complete Sequenced Command Cheatsheet (Line-by-Line Comments)

Below is the complete sequence of operational utility commands with detailed line-by-line comments explaining what each command accomplishes.

```bash
# ══════════════════════════════════════════════════════════════════════════════
# SECTION A: LOCAL MAC TERMINAL COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

# Check current active GCP account and project configuration
gcloud config list
# Output shows active account (e.g. jmlahmdpp225@gmail.com) and active project (peopleverdict-696f3)

# List all compute instances in the project along with their status and IP addresses
gcloud compute instances list --project=peopleverdict-696f3
# Shows instance name, zone, internal IP (10.160.0.2), external IP (8.234.93.21), and status (RUNNING/TERMINATED)

# Start the stopped VM instance to resume operations
gcloud compute instances start ai-fashion-designer --zone=asia-south1-a --project=peopleverdict-696f3
# Boots up the VM instance so it gets an IP address and starts accepting SSH connections

# Stop the running VM instance to pause billing when done working
gcloud compute instances stop ai-fashion-designer --zone=asia-south1-a --project=peopleverdict-696f3
# Shuts down the VM instance; stops compute billing charges while preserving disk data

# SSH into the running VM instance
gcloud compute ssh ai-fashion-designer --zone=asia-south1-a --project=peopleverdict-696f3
# Establishes a secure shell terminal session inside the Linux VM as user jamil.ahmad

# Securely copy local files/images to the VM instance
gcloud compute scp --recurse /Users/dev/ai-fasion-designer/test_images/* ai-fashion-designer:/srv/ai-fashion-designer/app/test_images/ --project=peopleverdict-696f3 --zone=asia-south1-a
# Recursively uploads all test images from your Mac to the VM's test_images directory

# List GCP firewall rules in project to verify port 80 (HTTP) and 443 (HTTPS) access
gcloud compute firewall-rules list --project=peopleverdict-696f3
# Verifies that allow-http (port 80) and allow-https (port 443) rules exist and are active

# ══════════════════════════════════════════════════════════════════════════════
# SECTION B: INSIDE VM SSH TERMINAL COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

# Check status of FastAPI backend systemd service
sudo systemctl status ai-fashion-backend
# Shows if uvicorn is active (running), memory usage, PID, and recent log snippets (press 'q' to exit)

# Start the FastAPI backend service
sudo systemctl start ai-fashion-backend
# Launches the uvicorn process running src.main:app on 127.0.0.1:8083 in the background

# Stop the FastAPI backend service
sudo systemctl stop ai-fashion-backend
# Gracefully terminates the uvicorn backend process

# Restart the FastAPI backend service
sudo systemctl restart ai-fashion-backend
# Restarts uvicorn to reload environment variables or backend Python code changes

# Tail live streaming backend logs in real time
sudo journalctl -u ai-fashion-backend -f
# Continuously outputs new log entries (useful for tracking API calls and LLM steps; press Ctrl+C to exit)

# Print last 50 lines of backend logs without auto-scrolling
sudo journalctl -u ai-fashion-backend -n 50 --no-pager
# Output latest 50 lines to terminal prompt without opening a pager

# Check status of Nginx web server
sudo systemctl status nginx
# Verifies if Nginx is active and listening on ports 80 and 443 (press 'q' to exit)

# Test Nginx configuration syntax for errors
sudo nginx -t
# Validates syntax of /etc/nginx/sites-available/ai-fashion-designer before reloading

# Reload Nginx configuration without dropping connections
sudo systemctl reload nginx
# Applies updated Nginx site configuration or SSL certificate changes instantly

# Test backend health endpoint directly on localhost
curl http://127.0.0.1:8083/v1/health
# Returns JSON {"status":"healthy","pinecone":"connected","version":"0.1.0"} directly from FastAPI

# Test Nginx reverse proxy health endpoint on localhost
curl http://localhost/v1/health
# Returns health JSON forwarded through Nginx proxy to uvicorn

# Check installed SSL certificate details for nip.io domain
sudo certbot certificates
# Displays cert name (8.234.93.21.nip.io), expiry date, and certificate file paths
