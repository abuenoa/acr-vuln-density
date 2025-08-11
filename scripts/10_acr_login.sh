#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../.env"
az acr login -n "$ACR_NAME"
echo "Logged into $ACR_NAME ($LOGIN_SERVER)"
