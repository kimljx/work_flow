#!/usr/bin/env bash
set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-work-flow-db}"
STOP_DB="${STOP_DB:-false}"

podman rm -f work-flow >/dev/null 2>&1 || true
echo "Application container stopped."

if [[ "$STOP_DB" == "true" ]]; then
  podman rm -f "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
  echo "PostgreSQL container stopped."
else
  echo "PostgreSQL container is still running. Use STOP_DB=true bash stop_project.sh to stop it."
fi
