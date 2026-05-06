#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
python3 deploy/offline/build_linux_offline_package.py
