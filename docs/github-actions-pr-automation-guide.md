# GitHub Actions PR Automation & On-Demand Ephemeral Deployment Guide

## 1. Why Job #3 and Job #4 Show "This job was skipped" on Automatic PR Builds

When a Pull Request is opened or updated, GitHub Actions triggers automatically with event `pull_request`.
- Jobs 1 (`semgrep-security-scan`) and 2 (`build-and-verify`) run automatically to fulfill security guardrails and PR checks.
- Jobs 3 (`ephemeral-sanity-check`) and 4 (`gcp-vm-deploy`) are **intentionally skipped** during automatic PR checks so that server setups do not run unnecessarily on every single code commit.
- Clicking **"Re-run all jobs"** on an automatic PR run re-runs the PR event, so Jobs 3 and 4 remain skipped.

---

## 2. How to Trigger Job #3 (Ephemeral Sanity Test) On-Demand

You have **two easy ways** to run Job #3 on demand whenever you want:

### Method A: Via GitHub PR Label (Right inside the PR Page!)
1. Open your PR page on GitHub (e.g. [PR #11](https://github.com/jamil225/ai-fasion-designer/pull/11)).
2. On the right sidebar, click **Labels**.
3. Add the label: `run-sanity-check` (or `deploy-gcp` for GCP VM deployment).
4. GitHub Actions will immediately trigger the workflow run and execute **Job #3** (or **Job #4**)!

---

### Method B: Via "Run workflow" Button (Actions Tab)
1. Go to the **Actions** tab on GitHub: `https://github.com/jamil225/ai-fasion-designer/actions`
2. In the left sidebar under workflows, click **PR Automation, Build & On-Demand Deployment**.
3. Near the top right of the page, click the **"Run workflow"** button dropdown.
4. Choose your branch (e.g. `feat/ci-cd-on-demand-pr-automation` or `main`).
5. Select `execution_mode: ephemeral_sanity_check`.
6. Click the green **"Run workflow"** button.

---

## 3. Workflow Job Execution Summary

| Trigger | Mode / Condition | Executed Jobs |
|---|---|---|
| **Automatic PR Push** | Default PR update | Jobs 1 & 2 only (Jobs 3 & 4 skipped) |
| **PR Label Added** | Label: `run-sanity-check` | Jobs 1, 2, and **Job 3 (Ephemeral Sanity Test)** |
| **PR Label Added** | Label: `deploy-gcp` | Jobs 1, 2, and **Job 4 (GCP VM Deploy)** |
| **Actions Tab Button** | `execution_mode: ephemeral_sanity_check` | Jobs 1, 2, and **Job 3 (Ephemeral Sanity Test)** |
| **Actions Tab Button** | `execution_mode: gcp_vm_deploy` | Jobs 1, 2, and **Job 4 (GCP VM Deploy)** |
