#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ARCHIVE="$ROOT/images/playwright-python-v1.52.0-jammy.tar"
APP_RUNTIME_ARCHIVE="$ROOT/images/work-flow-runtime-playwright-1.52.tar"
POSTGRES_ARCHIVE="$ROOT/images/postgres-16-alpine.tar"
RUNTIME_SOURCE_TAG="mcr.microsoft.com/playwright/python:v1.52.0-jammy"
POSTGRES_SOURCE_TAG="docker.io/library/postgres:16-alpine"
RUNTIME_TAG="localhost/work-flow-runtime:playwright-1.52"
POSTGRES_TAG="localhost/work-flow-postgres:16-alpine"

if [[ "$(id -u)" != "0" ]]; then
  echo "Please run as root: sudo bash load_and_build_image.sh" >&2
  exit 1
fi

if [[ ! -f "$APP_RUNTIME_ARCHIVE" && ! -f "$RUNTIME_ARCHIVE" ]]; then
  echo "Missing offline Playwright image: $RUNTIME_ARCHIVE" >&2
  exit 1
fi

if [[ ! -f "$POSTGRES_ARCHIVE" ]]; then
  echo "Missing offline PostgreSQL image: $POSTGRES_ARCHIVE" >&2
  exit 1
fi

if [[ -f "$APP_RUNTIME_ARCHIVE" ]]; then
  echo "[1/4] Loading Work Flow runtime image"
  podman load -i "$APP_RUNTIME_ARCHIVE"
else
  echo "[1/4] Loading Playwright runtime image"
  podman load -i "$RUNTIME_ARCHIVE"

  echo "[2/4] Tagging runtime image as $RUNTIME_TAG"
  podman tag "$RUNTIME_SOURCE_TAG" "$RUNTIME_TAG"
fi

echo "[3/4] Loading PostgreSQL image"
podman load -i "$POSTGRES_ARCHIVE"

echo "[4/4] Tagging PostgreSQL image as $POSTGRES_TAG"
podman tag "$POSTGRES_SOURCE_TAG" "$POSTGRES_TAG"

echo
echo "Images are ready:"
echo "  - $RUNTIME_TAG"
echo "  - $POSTGRES_TAG"
