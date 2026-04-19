#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PIP_CONFIG_FILE="${PIP_CONFIG_FILE:-$(pwd)/pip.conf}"
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
echo "Done. Activate with: source .venv/bin/activate"
