#!/usr/bin/env bash
set -euo pipefail

echo "[install.sh] start (A-plan: keep template python, torch2.2)"
PY_BIN="${PY_BIN:-python3}"
TORCH_VENV="${TORCH_VENV:-/opt/venv_torch}"
RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"

echo "[install.sh] PY_BIN=$PY_BIN"
echo "[install.sh] TORCH_VENV=$TORCH_VENV"
echo "[install.sh] RFDIFFUSION_DIR=$RFDIFFUSION_DIR"

$PY_BIN --version

# --- OS deps ---
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential pkg-config ca-certificates curl git unzip wget \
  python3-venv python3-dev

# --- create venv if missing ---
if [ ! -x "$TORCH_VENV/bin/python" ]; then
  echo "[install.sh] creating venv at $TORCH_VENV"
  $PY_BIN -m venv "$TORCH_VENV"
fi

# --- upgrade base tooling ---
"$TORCH_VENV/bin/python" -m pip install -U pip setuptools wheel

# --- IMPORTANT: numpy<2 (torch 2.2 + 일부 바이너리 모듈 이슈 방지) ---
"$TORCH_VENV/bin/python" -m pip install "numpy<2"

# --- torch 2.2.0 + cu121 ---
"$TORCH_VENV/bin/python" -m pip install \
  --index-url https://download.pytorch.org/whl/cu121 \
  torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0

# --- DGL (torch 2.2 / cu121 wheel repo) ---
"$TORCH_VENV/bin/python" -m pip install \
  -f https://data.dgl.ai/wheels/torch-2.2/cu121/repo.html \
  dgl

# --- clone RFdiffusion if missing ---
if [ ! -d "$RFDIFFUSION_DIR" ]; then
  echo "[install.sh] RFdiffusion code not found at $RFDIFFUSION_DIR. Cloning..."
  git clone https://github.com/RosettaCommons/RFdiffusion.git "$RFDIFFUSION_DIR"
fi

# --- install SE3Transformer (RFdiffusion dependency) ---
# RFdiffusion 공식 설치 흐름: env/SE3Transformer 설치 후, 루트 pip install -e .
if [ -d "$RFDIFFUSION_DIR/env/SE3Transformer" ]; then
  echo "[install.sh] installing SE3Transformer from $RFDIFFUSION_DIR/env/SE3Transformer"
  pushd "$RFDIFFUSION_DIR/env/SE3Transformer" >/dev/null
  if [ -f requirements.txt ]; then
    "$TORCH_VENV/bin/python" -m pip install -r requirements.txt
  fi
  # setup.py 기반 설치
  "$TORCH_VENV/bin/python" -m pip install .
  popd >/dev/null
else
  echo "[install.sh] WARN: $RFDIFFUSION_DIR/env/SE3Transformer not found. se3-transformer install may fail."
fi

# --- install RFdiffusion python deps (editable) ---
echo "[install.sh] installing RFdiffusion (editable)"
pushd "$RFDIFFUSION_DIR" >/dev/null
"$TORCH_VENV/bin/python" -m pip install -e .
popd >/dev/null

# --- sanity check ---
echo "[install.sh] sanity check"
"$TORCH_VENV/bin/python" - <<'PY'
import sys
import numpy as np
import torch
import dgl
print("python:", sys.version.split()[0])
print("numpy :", np.__version__)
print("torch :", torch.__version__, "cuda:", torch.version.cuda, "avail:", torch.cuda.is_available())
print("dgl   :", dgl.__version__)
PY

echo "[install.sh] done"