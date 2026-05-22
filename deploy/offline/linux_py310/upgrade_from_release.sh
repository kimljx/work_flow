#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
This release uses PostgreSQL as the persistent data store.

Because the project has not gone live, legacy SQLite/config-file upgrade is no
longer performed by this script. Deploy the new release with the Podman
PostgreSQL scheme and keep the host data directory:

  /data/sql/postgre

For future releases, upgrade by extracting the new app package and pointing the
same Podman scripts at the new release directory. Do not copy app.db,
config/runtime-settings.json, or config/mail-hosts.json into the new release.
EOF
