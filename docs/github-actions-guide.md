# On-Demand GitHub Actions Setup & Usage Guide

> **Workflow File**: `.github/workflows/deploy-gcp.yml`  
> **Trigger**: Manual (`workflow_dispatch` — "Run workflow" button)  
> **Stages**: 1. Semgrep SAST ➔ 2. Build Verification ➔ 3. GCP VM Deploy  
> **Quota Usage**: **0 Minutes Consumed from Paid Limit** (Public Repositories on GitHub get unlimited free minutes!).

---

## 1. GitHub Free Plan Analysis

| Question | GitHub Free Plan Details |
|---|---|
| **Is the minute limit per-repo or per-account?** | The free minute limit is **shared across your entire GitHub account** (all repos under your account). |
| **What is the free minute limit?** | For **Public Repositories** (like `jamil225/ai-fasion-designer`), GitHub Actions is **100% FREE with UNLIMITED minutes**! For private repos, GitHub provides 2,000 free minutes per month per account. |
| **Why use `workflow_dispatch` (Manual Trigger)?** | Using `workflow_dispatch` gives you a **manual "Run workflow" button** in the GitHub UI so you run scans, builds, and deployments strictly when you decide, preventing unintended automatic runs on every minor edit. |

---

## 2. One-Time Setup: Adding GitHub Secrets

To allow Stage 3 (GCP VM Deployment) to SSH into your VM securely, add 3 secrets to your GitHub repository:

1. Go to your GitHub repository: **https://github.com/jamil225/ai-fasion-designer**
2. Click **Settings** (top bar) ➔ **Secrets and variables** (left sidebar) ➔ **Actions**
3. Click **New repository secret** for each of the following:

| Secret Name | Value | Description |
|---|---|---|
| `GCP_VM_IP` | `8.234.93.21` (or `8.234.93.21.nip.io`) | Your GCP VM's IP address or domain |
| `GCP_VM_USER` | `jamil.ahmad` | Your VM SSH username (run `whoami` on VM) |
| `GCP_SSH_KEY` | *(Contents of your SSH private key)* | Private SSH key used to access the VM |

---

## 3. How to Trigger the Manual Workflow (Run Button)

### Method A: From GitHub Browser UI (Any PR or Branch)

1. Go to: **https://github.com/jamil225/ai-fasion-designer/actions**
2. In the left sidebar, click **"Manual Build & GCP VM Deployment"**.
3. On the right side, click the **"Run workflow"** drop-down button:
   - Select the **Branch or PR branch** you want to test/deploy (e.g. `feat/gcp-deployment` or `agentic-implementation`).
   - Choose whether to deploy to GCP after build verification (`true` / `false`).
4. Click the blue **"Run workflow"** button.

### Method B: From GitHub CLI (`gh`)

```bash
# Run workflow on target branch
gh workflow run deploy-gcp.yml --ref feat/gcp-deployment

# View live execution logs
gh run watch
```

---

## 4. Workflow Pipeline Stages Explained

```
1. Semgrep SAST Scan  ──(Passes)──►  2. Build Verification  ──(Passes)──►  3. GCP VM Deploy
 (Scans for secrets    (Python requirements &       (SSHs into VM, pulls code,
  & security bugs)      Vite React compilation)      rebuilds frontend, restarts backend)
```

- **Stage 1 (Semgrep Scan)**: Scans your code for secret leaks, hardcoded credentials, and security bugs. If a security bug is detected, execution stops.
- **Stage 2 (Build Verification)**: Sets up Python 3.12 & Node 20, verifies backend packages, and compiles Vite React static assets to verify build integrity.
- **Stage 3 (GCP VM Deploy)**: SSHs into your GCE VM, pulls the latest code, updates `/var/www/ai-fashion-designer`, and restarts `ai-fashion-backend` systemd service.
