#!/usr/bin/env bash
set -euo pipefail
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1"; exit 1; }; }
need az; need docker; need jq; need trivy; need awk; need sed; need python3
echo "Docker: $(docker --version)"
echo "Azure CLI: $(az version --query azure-cli -o tsv)"
echo "jq: $(jq --version)"
trivy -v
python3 --version
