#!/usr/bin/env bash
# Usage: 30_scan_images.sh T0|T1|T2|T3
set -euo pipefail
TP="${1:?Timepoint (T0|T1|T2|T3) required}"

source "$(dirname "$0")/../.env"
mkdir -p "$(dirname "$0")/../data/json" "$(dirname "$0")/../data/csv"

CSV="data/csv/resultados_${TP,,}.csv"
JSON_DIR="data/json"
DATE_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# fixed image set (as per proposal)
IMAGES=(
  "${LOGIN_SERVER}/alpine:v1 alpine v1"
  "${LOGIN_SERVER}/debian-slim:v1 debian-slim v1"
  "${LOGIN_SERVER}/ubuntu:v1 ubuntu v1"
  "${LOGIN_SERVER}/busybox:v1 busybox v1"
)

# header if missing
if [ ! -f "$CSV" ]; then
  echo "timepoint,image,tag,repo,image_ref,size_mb,cv_critical,cv_high,density,trivy_db_updated_at,trivy_version,scan_utc" > "$CSV"
fi

# record Trivy meta once (will also be parsed per row)
TRIVY_META="$(trivy -v | sed 's/[[:space:]]\{1,\}/ /g')"
TRIVY_VERSION="$(echo "$TRIVY_META" | awk '/Version:/ {print $2}')"
DB_UPDATED="$(echo "$TRIVY_META" | awk -F': ' '/Vulnerability DB:/ {print $2}')"

for entry in "${IMAGES[@]}"; do
  read -r IMAGE REPO TAG <<<"$entry"
  echo "== Pulling $IMAGE"
  docker pull "$IMAGE" >/dev/null

  SIZE_BYTES="$(docker image inspect "$IMAGE" --format='{{ .Size }}')"
  SIZE_MB="$(awk -v s="$SIZE_BYTES" 'BEGIN { printf "%.2f", s/1048576 }')"

  OUT_JSON="${JSON_DIR}/trivy_${REPO}_${TAG}_${TP}.json"
  echo "== Trivy scan $IMAGE -> $OUT_JSON"
  trivy image --quiet --severity CRITICAL,HIGH --format json "$IMAGE" > "$OUT_JSON"

  # jq with null-safety across Results[].Vulnerabilities
  CRIT=$(jq '[.Results[]? | (.Vulnerabilities // [])[] | select(.Severity=="CRITICAL")] | length' "$OUT_JSON")
  HIGH=$(jq '[.Results[]? | (.Vulnerabilities // [])[] | select(.Severity=="HIGH")]     | length' "$OUT_JSON")

  # density per MB (avoid div-by-zero)
  DENSITY="$(awk -v c="$CRIT" -v h="$HIGH" -v mb="$SIZE_MB" 'BEGIN{ if(mb>0){ printf "%.6f", (c+h)/mb } else { print "NA" } }')"

  echo "${TP},${REPO},${TAG},${REPO},${IMAGE},${SIZE_MB},${CRIT},${HIGH},${DENSITY},${DB_UPDATED},${TRIVY_VERSION},${DATE_UTC}" \
    >> "$CSV"
done

echo "Saved -> $CSV"
