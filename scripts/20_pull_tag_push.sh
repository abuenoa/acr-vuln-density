#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../.env"

# <source_ref> <repo> <tag>
IMAGES=(
  "alpine:3.18 alpine v1"
  "debian:bookworm-slim debian-slim v1"
  "ubuntu:22.04 ubuntu v1"
  "busybox:1.35 busybox v1"
)

for entry in "${IMAGES[@]}"; do
  read -r SRC REPO TAG <<<"$entry"

  echo "== Pulling $SRC from Docker Hub"
  docker pull "$SRC"

  TARGET="${LOGIN_SERVER}/${REPO}:${TAG}"
  echo "== Tagging -> $TARGET"
  docker tag "$SRC" "$TARGET"

  echo "== Pushing -> $TARGET"
  docker push "$TARGET"
done
