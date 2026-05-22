#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RELEASE_DIR="${1:-/data/work_flow/current}"
APP_PORT="${APP_PORT:-18849}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-localhost/work-flow-postgres:16-alpine}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-work-flow-db}"
POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-15432}"
POSTGRES_DB="${POSTGRES_DB:-work_flow}"
POSTGRES_USER="${POSTGRES_USER:-work_flow}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-work_flow_change_me}"
RUNTIME_IMAGE="${RUNTIME_IMAGE:-localhost/work-flow-runtime:playwright-1.52}"
START_SCRIPT="$ROOT/container/start-work-flow-container.sh"
POSTGRES_DATA_DIR="${POSTGRES_DATA_DIR:-/data/sql/postgre}"

if [[ "$(id -u)" != "0" ]]; then
  echo "Please run as root: sudo APP_PORT=$APP_PORT bash run_project.sh $RELEASE_DIR" >&2
  exit 1
fi

if [[ ! -d "$RELEASE_DIR" ]]; then
  echo "Release directory not found: $RELEASE_DIR" >&2
  exit 1
fi

if [[ ! -x "$RELEASE_DIR/runtime/python/bin/python3.10" ]]; then
  echo "Bundled Python runtime is not executable: $RELEASE_DIR/runtime/python/bin/python3.10" >&2
  exit 1
fi

if [[ ! -f "$START_SCRIPT" ]]; then
  echo "Container start script not found: $START_SCRIPT" >&2
  exit 1
fi

mkdir -p \
  "$RELEASE_DIR/local/logs" \
  "$RELEASE_DIR/local/run" \
  "$RELEASE_DIR/local/cache" \
  "$RELEASE_DIR/local/temp" \
  "$RELEASE_DIR/local/home" \
  "$POSTGRES_DATA_DIR"

podman rm -f work-flow >/dev/null 2>&1 || true

if ! podman ps --format '{{.Names}}' | grep -qx "$POSTGRES_CONTAINER"; then
  podman rm -f "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
  podman run -d \
    --name "$POSTGRES_CONTAINER" \
    --network host \
    --security-opt label=disable \
    -e POSTGRES_DB="$POSTGRES_DB" \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -v "$POSTGRES_DATA_DIR:/var/lib/postgresql/data:Z" \
    "$POSTGRES_IMAGE" \
    postgres -p "$POSTGRES_PORT"
fi

echo "Waiting for PostgreSQL on $POSTGRES_HOST:$POSTGRES_PORT ..."
for _ in $(seq 1 60); do
  if podman exec "$POSTGRES_CONTAINER" pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! podman exec "$POSTGRES_CONTAINER" pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
  echo "PostgreSQL did not become ready. Check: podman logs $POSTGRES_CONTAINER" >&2
  exit 1
fi

DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"

podman run -d \
  --name work-flow \
  --network host \
  --privileged \
  --security-opt label=disable \
  -e APP_PORT="$APP_PORT" \
  -e DATABASE_URL="$DATABASE_URL" \
  -v "$RELEASE_DIR:/opt/work_flow:Z" \
  -v "$START_SCRIPT:/usr/local/bin/start-work-flow-container:ro,Z" \
  "$RUNTIME_IMAGE" \
  bash /usr/local/bin/start-work-flow-container

echo "Started containers: work-flow, $POSTGRES_CONTAINER"
echo "URL: http://<server-ip>:$APP_PORT"
echo "PostgreSQL data directory: $POSTGRES_DATA_DIR"
echo "Logs: podman logs -f work-flow"
