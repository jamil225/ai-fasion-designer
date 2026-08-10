# GitHub Actions PR Automation & On-Demand Ephemeral Deployment Guide

## 1. Overview & Answers to Key Architecture Questions

### Q1: Will the build happen on the VM provided by GitHub?
**Yes, absolutely.** 
When GitHub Actions triggers a workflow run (whether on a Pull Request or via manual button trigger), GitHub provisions a fresh, temporary Virtual Machine in Azure/GitHub Cloud running `ubuntu-latest`.
Inside this GitHub-provided VM:
1. Your repository code is checked out.
2. Python 3.12 and Node.js 20 environments are set up.
3. Backend dependencies are installed (`pip install -r requirements.txt`).
4. Frontend React assets are compiled (`npm run build`).
5. Security scans (`semgrep`) and build verification are performed.

Once the job finishes, GitHub automatically **wipes and destroys** the runner VM.

---

### Q2: Can I get a GitHub-provided VM to deploy my app for testing, perform a health check, and close/destroy the app on-demand only when I click a button (not automatically on push)?
**Yes, exactly!**
In our updated workflow `.github/workflows/deploy-gcp.yml`:
1. **On Pull Request (`on: pull_request`)**:
   - The workflow runs **Build Verification** and **Semgrep Security Scanning** automatically to enforce PR guardrails and required status checks.
   - It **does NOT** deploy to GCP or keep test servers running automatically.
2. **On-Demand Manual Trigger (`workflow_dispatch`)**:
   - In the GitHub UI (Actions tab or PR actions menu), you click the **"Run workflow"** button on demand.
   - You can select `execution_mode: ephemeral_sanity_check`:
     - GitHub spins up a runner VM.
     - Builds your backend and frontend.
     - Starts `uvicorn src.main:app` on port 8083.
     - Sends a request to `http://127.0.0.1:8083/v1/health` and verifies `HTTP 200 OK`.
     - Logs the health status JSON output.
     - Gracefully terminates the uvicorn process and tears down/closes the GitHub runner VM.

---

## 2. Workflow Trigger Summary

| Trigger | Mode | Action Performed |
|---|---|---|
| **Pull Request** (`pull_request`) | Automatic on PR open/update | Runs Semgrep SAST scan (`semgrep-security-scan`) and builds backend/frontend (`build-and-verify`). Does **not** deploy. |
| **Manual Button** (`workflow_dispatch`) | `ephemeral_sanity_check` | Builds app, launches FastAPI on GitHub Runner VM, runs `/v1/health` check, logs output, and destroys runner VM. |
| **Manual Button** (`workflow_dispatch`) | `gcp_vm_deploy` | SSHs into GCP VM (`ai-fashion-designer-vm`), updates code, rebuilds assets, restarts `ai-fashion-backend` systemd service, and verifies live HTTPS status. |

---

## 3. How to Trigger On-Demand Deployment & Sanity Check from GitHub UI

1. Open your repository on GitHub: `https://github.com/jamil225/ai-fasion-designer`
2. Navigate to the **Actions** tab.
3. Select **PR Automation, Build & On-Demand Deployment** from the left workflow list.
4. Click the **Run workflow** dropdown on the right:
   - Select your target branch (e.g. `feat/ci-cd-on-demand-pr-automation` or `main`).
   - Select execution mode: `ephemeral_sanity_check` or `gcp_vm_deploy`.
   - Click **Run workflow**.
