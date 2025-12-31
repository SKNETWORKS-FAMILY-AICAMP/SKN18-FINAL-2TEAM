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

# --- RFdiffusion 런타임에서 실제로 필요했던 deps (너가 수동 설치로 해결한 것들) ---
# opt_einsum: se3/e3nn 쪽에서 종종 필요, pyrsistent: symmetry.py에서 필요, e3nn: se3_transformer가 필요
"$TORCH_VENV/bin/python" -m pip install -U opt_einsum pyrsistent e3nn

# --- clone RFdiffusion if missing ---
if [ ! -d "$RFDIFFUSION_DIR" ]; then
  echo "[install.sh] RFdiffusion code not found at $RFDIFFUSION_DIR. Cloning..."
  git clone https://github.com/RosettaCommons/RFdiffusion.git "$RFDIFFUSION_DIR"
fi

# --- install SE3Transformer (가장 재현성 좋게: NVIDIA DeepLearningExamples 경로 우선) ---
echo "[install.sh] installing se3-transformer (preferred: NVIDIA DeepLearningExamples)"
if "$TORCH_VENV/bin/python" -c "import se3_transformer" >/dev/null 2>&1; then
  echo "[install.sh] se3_transformer already importable. Skipping."
else
  # opt_einsum 최신화(가끔 필요)
  "$TORCH_VENV/bin/python" -m pip install -U opt_einsum

  # NVIDIA DeepLearningExamples의 SE3Transformer 설치
  "$TORCH_VENV/bin/python" -m pip install -U \
    "git+https://github.com/NVIDIA/DeepLearningExamples.git#subdirectory=DGLPyTorch/DrugDiscovery/SE3Transformer" \
  || true

  # 그래도 안되면 RFdiffusion repo 내부 env/SE3Transformer fallback
  if ! "$TORCH_VENV/bin/python" -c "import se3_transformer" >/dev/null 2>&1; then
    if [ -d "$RFDIFFUSION_DIR/env/SE3Transformer" ]; then
      echo "[install.sh] fallback: installing SE3Transformer from $RFDIFFUSION_DIR/env/SE3Transformer"
      pushd "$RFDIFFUSION_DIR/env/SE3Transformer" >/dev/null
      if [ -f requirements.txt ]; then
        "$TORCH_VENV/bin/python" -m pip install -r requirements.txt
      fi
      "$TORCH_VENV/bin/python" -m pip install .
      popd >/dev/null
    else
      echo "[install.sh] ERROR: cannot install se3-transformer (no fallback dir found)" >&2
      exit 2
    fi
  fi
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
import e3nn
import pyrsistent
import se3_transformer

print("python:", sys.version.split()[0])
print("numpy :", np.__version__)
print("torch :", torch.__version__, "cuda:", torch.version.cuda, "avail:", torch.cuda.is_available())
print("dgl   :", dgl.__version__)
print("e3nn  :", getattr(e3nn, "__version__", "unknown"))
print("pyrsistent import: OK")
print("se3_transformer import: OK")
PY

echo "[install.sh] done"