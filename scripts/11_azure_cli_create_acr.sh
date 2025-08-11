#!/usr/bin/env bash
set -euo pipefail

# ================================================
# Azure CLI ACR Creation Helper (Bash)
# Creates a Resource Group and an Azure Container Registry (ACR)
# Tries multiple candidate regions in case subscription policies block some
# Generates a `.env` file with ACR_NAME and LOGIN_SERVER for the rest of the pipeline
# ================================================

# ---- Configuration ----
PREFIX="${PREFIX:-tfm}"                # Prefix for resource names (can be overridden via environment variable)
RG_LOCATION="${RG_LOCATION:-westeurope}"  # Location for the Resource Group
CANDIDATES=(                            # Candidate regions for ACR creation
  uksouth
  northeurope
  eastus
  francecentral
  swedencentral
  germanywestcentral
)

# ---- Step 1: Ensure Azure login ----
echo "== [1/4] Checking Azure login =="
if ! az account show >/dev/null 2>&1; then
  az login --use-device-code
fi

# ---- Step 2: Create or ensure Resource Group exists ----
RG_NAME="${PREFIX}-rg"
echo "== [2/4] Creating/ensuring Resource Group: $RG_NAME in $RG_LOCATION =="
az group create -n "$RG_NAME" -l "$RG_LOCATION" -o none

# ---- Step 3: Generate unique suffix for ACR name ----
# Azure ACR names must be globally unique, so we add a random suffix
SUFFIX="$(tr -dc 'a-z0-9' </dev/urandom | head -c 6 || echo $RANDOM)"
ACR_NAME="${PREFIX}acr${SUFFIX}"

echo "== [3/4] Attempting ACR creation in candidate regions =="

# ---- Step 4: Try creating ACR in each candidate region until one works ----
for region in "${CANDIDATES[@]}"; do
  echo "   → Trying region: $region"
  
  if az acr create -g "$RG_NAME" -n "$ACR_NAME" -l "$region" --sku Basic --admin-enabled true -o none; then
    # If creation succeeds, get the login server URL
    LOGIN_SERVER="$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)"
    
    echo "✅ ACR created: $ACR_NAME ($LOGIN_SERVER) in $region"
    
    # Write credentials to .env file for later scripts
    printf "ACR_NAME=%s\nLOGIN_SERVER=%s\n" "$ACR_NAME" "$LOGIN_SERVER" > .env
    
    echo "== Generated .env file =="
    cat .env
    
    echo "== [4/4] Current repositories in ACR (should be empty for a new registry) =="
    az acr repository list -n "$ACR_NAME" -o table
    
    exit 0
  else
    echo "   ❌ Region $region failed, trying next..."
  fi
done

# If all regions failed:
echo "❌ ERROR: Could not create ACR in any candidate region" >&2
exit 1
