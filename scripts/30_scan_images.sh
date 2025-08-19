#!/usr/bin/env bash
set -euo pipefail

# Main script: scans base images stored in ACR and saves Trivy results
# Usage: bash scripts/30_scan_images.sh T0|T1|T2|T3

TIMEPOINT="${1:?Usage: $0 <T0|T1|T2|T3>}"

source .env

OUT_JSON_DIR="data/json"
OUT_CSV="data/csv/resultados_${TIMEPOINT}.csv"
mkdir -p "$OUT_JSON_DIR" data/csv

echo "timepoint,image,tag,repo,image_ref,size_mb,cv_critical,cv_high,density,trivy_db_updated_at,trivy_version,scan_utc" > "$OUT_CSV"

IMAGES=("alpine:v1" "debian-slim:v1" "ubuntu:v1" "busybox:v1")

for IMG in "${IMAGES[@]}"; do
  REPO="${LOGIN_SERVER}"
  TAG="${IMG##*:}"
  IMAGE_REF="${LOGIN_SERVER}/${IMG}"

  echo "== Pulling ${IMAGE_REF} =="
  if ! docker pull "${IMAGE_REF}"; then
    echo "ERROR: Failed to pull ${IMAGE_REF}" >&2
    continue
  fi

  SIZE_BYTES=$(docker image inspect "${IMAGE_REF}" --format='{{.Size}}' || echo 0)
  SIZE_MB=$(echo "$SIZE_BYTES" | awk '{printf "%.2f", $1 / 1024 / 1024}')

  TRIVY_JSON="${OUT_JSON_DIR}/trivy_${REPO}_${TAG}_${TIMEPOINT}.json"
  echo "== Scanning ${IMAGE_REF} =="
  if ! trivy image --quiet --severity CRITICAL,HIGH --format json -o "$TRIVY_JSON" "$IMAGE_REF"; then
    echo "ERROR: Trivy failed for ${IMAGE_REF}" >&2
    continue
  fi

  if [ ! -s "$TRIVY_JSON" ]; then
    echo "ERROR: Empty JSON for ${IMAGE_REF}, skipping." >&2
    continue
  fi

  # Safe parsing with jq: handle nulls or missing keys gracefully
  CV_CRITICAL=$(jq '[.Results[]? | select(.Vulnerabilities) | .Vulnerabilities[]? | select(.Severity=="CRITICAL")] | length' "$TRIVY_JSON" || echo 0)
  CV_HIGH=$(jq '[.Results[]? | select(.Vulnerabilities) | .Vulnerabilities[]? | select(.Severity=="HIGH")] | length' "$TRIVY_JSON" || echo 0)

  DENSITY=$(echo "$CV_CRITICAL $CV_HIGH $SIZE_MB" | awk '{total=$1+$2; if ($3==0) print 0; else printf "%.4f", total/$3}')

  # Extract Trivy version and DB updatedAt correctly
  TRIVY_VERSION=$(trivy --version | awk -F': ' '/Version:/ && !found {print $2; found=1}')
  TRIVY_DB_UPDATED=$(trivy --version | awk -F': ' '/UpdatedAt:/ {print $2}')

  SCAN_TIME_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  echo "${TIMEPOINT},${REPO},${TAG},${LOGIN_SERVER},${IMAGE_REF},${SIZE_MB},${CV_CRITICAL},${CV_HIGH},${DENSITY},${TRIVY_DB_UPDATED},${TRIVY_VERSION},${SCAN_TIME_UTC}" >> "$OUT_CSV"
done

echo "✅ Scan completed for ${TIMEPOINT}. Results saved to ${OUT_CSV}"
