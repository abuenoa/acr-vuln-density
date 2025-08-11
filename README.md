# ACR Vulnerability Density (Trivy T0–T3)

Empirical, reproducible pipeline to analyse **vulnerability density** and **vulnerability drift** in base container images hosted in **Azure Container Registry (ACR)**. The workflow pulls images from Docker Hub, pushes them to ACR, scans them with **Trivy** at four timepoints (T0, T1, T2, T3), consolidates results, and generates figures ready to include in your MSc thesis.

> British English is used throughout. References are provided in Harvard style.

---

## Contents
- [Overview](#overview)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Local Python environment (pyenv)](#local-python-environment-pyenv)
- [Initial Git set-up (GitHub identity only for this repo)](#initial-git-set-up-github-identity-only-for-this-repo)
- [Provision Azure & push images](#provision-azure--push-images)
- [Run longitudinal scans](#run-longitudinal-scans)
- [Consolidate & visualise](#consolidate--visualise)
- [Outputs](#outputs)
- [Reproducibility & provenance](#reproducibility--provenance)
- [Simulation option](#simulation-option-if-you-cannot-wait-3-weeks)
- [Troubleshooting](#troubleshooting)
- [Project hygiene](#project-hygiene)
- [References (Harvard style)](#references-harvard-style)
- [Licence](#licence)

---

## Overview

**Goal.** Quantitatively measure vulnerability density and drift in common base images stored in ACR over four weekly timepoints.

**Images.**
- `alpine:3.18`
- `debian:bookworm-slim`
- `ubuntu:22.04`
- `busybox:1.35`

**Key metric.** Vulnerability density = (CRITICAL + HIGH) / size in MB (normalisation improves cross-image comparability).

**Design.** Experimental, longitudinal (T0–T3, weekly), reproducible. All runs record Trivy version and Vulnerability DB stamp.

---

## Repository structure

```
acr-vuln-density/
├─ terraform/                # ACR infra (RG + ACR, West Europe, Basic)
│  ├─ main.tf
│  └─ outputs.tf
├─ scripts/
│  ├─ 00_prereqs_check.sh    # verify tools; log versions
│  ├─ 10_acr_login.sh        # az acr login
│  ├─ 20_pull_tag_push.sh    # pull from Docker Hub; tag & push to ACR
│  ├─ 30_scan_images.sh      # Trivy scan for a given timepoint (T0/T1/T2/T3)
│  ├─ 31_scan_T0.sh
│  ├─ 32_scan_T1.sh
│  ├─ 33_scan_T2.sh
│  └─ 34_scan_T3.sh
├─ analysis/
│  ├─ merge_and_plot.py      # pandas consolidation + matplotlib figures
│  └─ requirements.txt
├─ data/
│  ├─ json/                  # raw Trivy JSON per image/timepoint (gitignored)
│  ├─ csv/                   # resultados_t*.csv + comparativa.csv (gitignored)
│  └─ fig/                   # generated figures (gitignored)
├─ Makefile
└─ README.md
```

---

## Prerequisites

- Docker Engine **20+**
- Terraform **1.4+**
- Azure CLI (logged in with access to create RG+ACR)
- `jq` **1.6**
- Trivy **0.45.1**
- Python **3.9+** (managed via `pyenv`)
- `git`, and SSH access to GitHub

Confirm prerequisites and capture a dated provenance log:
```bash
bash scripts/00_prereqs_check.sh | tee versions_$(date -u +%F).log
```

---

## Local Python environment (pyenv)

Create a dedicated interpreter and virtual environment for **this** repository (kept separate from other projects).

```bash
# Install interpreter (example: 3.9.19)
pyenv install 3.9.19

# Create virtualenv just for this repo
pyenv virtualenv 3.9.19 acr-vuln-density-3.9

# Activate automatically within this folder
pyenv local acr-vuln-density-3.9

# Install analysis dependencies
python -m pip install --upgrade pip wheel
pip install -r analysis/requirements.txt
```

> The file `.python-version` pins the environment so that entering this folder activates it automatically. Your other projects can use different `pyenv local` values without conflict.

---

## Initial Git set-up (GitHub identity only for this repo)

This repository is intended for **GitHub**. Configure a per-repo identity so it does not clash with other (e.g., GitLab) projects.

```bash
# Ensure the remote points to GitHub
git remote -v

# Set identity locally (repository-only)
git config user.name  "Your GitHub Name"
git config user.email "your-github-email@example.com"

# Optional: SSH separation (if you use different keys)
# ~/.ssh/config can specify a dedicated key for github.com
```

Recommended `.gitignore` additions (on top of the Python template):
```
.env
data/json/
data/csv/
data/fig/
versions_*.log
.terraform/
terraform.tfstate*
__pycache__/
*.pyc
```

---

## Provision Azure & push images

Create the resource group and ACR (West Europe, Basic SKU), log in, then mirror images into ACR.

```bash
make prereqs
make infra
bash scripts/10_acr_login.sh
make push
```

This will set two environment values in `.env`: `ACR_NAME` and `LOGIN_SERVER` (exported from Terraform outputs).

---

## Run longitudinal scans

Run the first scan today (**T0**), then repeat weekly for **T1**, **T2**, **T3**. Do not modify images between scans.

```bash
make t0     # Day 0
# wait ~7 days
make t1     # Day 7
# wait ~7 days
make t2     # Day 14
# wait ~7 days
make t3     # Day 21
```

Each run generates raw JSON files and a CSV per timepoint under `data/` (gitignored).

---

## Consolidate & visualise

After at least T0 is available (ideally after T3):

```bash
make analyse
```

This creates:
- `data/csv/comparativa.csv`
- Figures under `data/fig/`:
  - `density_T0_T3.png`
  - `cves_over_time_<image>.png`
  - `cum_growth_<image>.png`

---

## Outputs

- **Raw**: `data/json/trivy_<repo>_<tag>_<TP>.json`
- **Per-timepoint CSV**: `data/csv/resultados_t{0..3}.csv`
- **Consolidated CSV**: `data/csv/comparativa.csv`
- **Figures**: `data/fig/*.png`
- **Provenance logs**: `versions_YYYY-MM-DD.log`

Column schema (`resultados_t*.csv`):
```
timepoint,image,tag,repo,image_ref,size_mb,cv_critical,cv_high,density,trivy_db_updated_at,trivy_version,scan_utc
```

---

## Reproducibility & provenance

- Each scan records **UTC timestamp**, **Trivy version** and **Trivy Vulnerability DB** stamp (from `trivy -v`).  
- Toolchain versions are captured via `00_prereqs_check.sh`.  
- Scripts and infrastructure-as-code are committed to version control.  
- The metric definition (density per MB) ensures size-normalised comparability across heterogeneous images.

These practices allow independent replication and transparent interpretation of vulnerability drift.

---

## Simulation option (if you cannot wait 3 weeks)

If time-constrained, you may run T0–T3 consecutively on the same day to **simulate** timepoints. Clearly label results as simulated in your thesis; note that changes then reflect only Trivy DB refreshes occurring during the session (if any), not upstream image evolution.

---

## Troubleshooting

- **ACR login issues**  
  ```bash
  az acr login -n "$ACR_NAME"
  docker logout "$LOGIN_SERVER" && docker login "$LOGIN_SERVER"
  ```
- **Terraform state/permission errors**: ensure you are logged in (`az login`) and have access to create RG and ACR; re-run `make infra`.
- **Disk space**: keep at least 10 GB free for image layers and JSON outputs.
- **Trivy network/DB**: if DB download fails, retry the scan once connected to a stable network.

---

## Project hygiene

- Keep the repository clean: outputs and figures are **gitignored**.  
- Commit scripts and Terraform files with meaningful messages (e.g., `T1 scans + provenance`).  
- Use GitHub Issues to note decisions and record dates for T1–T3.

---

## References (Harvard style)

- Aqua Security (2022) *Trivy: A comprehensive vulnerability scanner*. Available at: https://github.com/aquasecurity/trivy (Accessed: 11 August 2025).
- Microsoft Docs (2024) *Azure Container Registry documentation*. Available at: https://learn.microsoft.com/azure/container-registry (Accessed: 11 August 2025).
- National Institute of Standards and Technology (2017) *NIST SP 800-190: Application Container Security Guide*. https://doi.org/10.6028/NIST.SP.800-190.
- Chacon, S. and Straub, B. (2021) *Pro Git*. 2nd edn. Apress. Available at: https://git-scm.com/book/en/v2 (Accessed: 11 August 2025).

---

## Licence

MIT License for the code in this repository. Trivy © Aqua Security; Docker and image trademarks belong to their respective owners.
