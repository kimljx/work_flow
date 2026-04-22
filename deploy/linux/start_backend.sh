#!/usr/bin/env bash
set -euo pipefail
mkdir -p ../../backend/data
PYTHONPATH=../../backend python3 -m uvicorn app.main:app --app-dir ../../backend --host 0.0.0.0 --port 8000
