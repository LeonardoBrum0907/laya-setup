#!/usr/bin/env bash
# macOS / Linux setup: creates .venv, installs PyTorch and the pinned laya.
#   bash scripts/setup.sh          # CPU (or MPS on Apple Silicon)
#   bash scripts/setup.sh --cuda   # NVIDIA GPU (CUDA 12.8 build)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python
$PY -m pip install --upgrade pip
if [ "${1:-}" = "--cuda" ]; then
  $PY -m pip install torch --index-url https://download.pytorch.org/whl/cu128
elif [ "$(uname)" = "Darwin" ]; then
  $PY -m pip install torch
else
  $PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu
fi
$PY -m pip install -r requirements.txt
$PY -I -c "import laya; print('laya', laya.__version__)"
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }
