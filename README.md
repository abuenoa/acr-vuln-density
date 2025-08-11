# ACR Vulnerability Density (Trivy T0–T3)

This repository hosts an automated and reproducible pipeline to:
- Pull base images from Docker Hub, push to Azure Container Registry (ACR).
- Scan with Trivy at T0/T1/T2/T3.
- Consolidate results and produce metrics/visualisations for vulnerability drift.

**Folders**
- `terraform/` — ACR provisioning.
- `scripts/` — Pull/tag/push and scan scripts.
- `analysis/` — Python consolidation and plots.
- `data/` — Raw JSON, CSV and figures (gitignored).
