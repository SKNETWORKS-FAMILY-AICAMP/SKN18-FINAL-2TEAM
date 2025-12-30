#!/usr/bin/env bash
# =========================
# RFdiffusion GPU stack pin (Torch venv)
# torch (cu117) + dgl (cu117) + numpy (1.26.x) + nvidia-cu11 runtime libs
# + venv bootstrap (auto-create) + verification snippet
# =========================
set -euo pipefail

echo "[install.sh] start"

# ---- Config ----
VENV_ROOT="${VENV_ROOT:-/opt/venv_torch}"
VENV_PY="${VENV_PY:-${VENV_ROOT}/bin/python}"
VENV_PIP="${VENV_PIP:-${VENV_ROOT}/bin/pip}"

echo "[install.sh] Target venv root: ${VENV_ROOT}"
echo "[install.sh] Using python: ${VENV_PY}"
echo "[install.sh] Using pip   : ${VENV_PIP}"

# ---- 0) venv bootstrap (create if missing) ----
if [[ ! -x "${VENV_PY}" ]]; then
  echo "[install.sh] venv not found -> creating: ${VENV_ROOT}"

  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-venv python3-pip python3-setuptools python3-wheel \
    && rm -rf /var/lib/apt/lists/*

  python3 -m venv "${VENV_ROOT}"
  "${VENV_PIP}" install -U pip
fi

# ---- sanity ----
"${VENV_PY}" -V
"${VENV_PIP}" -V

# ---- 1) clean conflicting installs (safe to ignore failures) ----
echo "[install.sh] Removing potentially conflicting packages..."
"${VENV_PIP}" uninstall -y dgl torch torchvision torchaudio || true

# ---- 2) pin numpy first (avoid numpy 2.x breakage with older compiled wheels) ----
echo "[install.sh] Pinning NumPy..."
"${VENV_PIP}" install -U "numpy==1.26.4"

# ---- 3) install PyTorch cu117 pinned versions ----
echo "[install.sh] Installing PyTorch CUDA 11.7 stack..."
"${VENV_PIP}" install --index-url https://download.pytorch.org/whl/cu117 \
  "torch==2.0.1+cu117" \
  "torchvision==0.15.2+cu117" \
  "torchaudio==2.0.2+cu117"

# ---- 4) install NVIDIA CUDA 11 runtime libs via pip ----
echo "[install.sh] Installing NVIDIA cu11 runtime libs (pip)..."
"${VENV_PIP}" install -U \
  nvidia-cuda-runtime-cu11 \
  nvidia-cublas-cu11 \
  nvidia-cusparse-cu11 \
  nvidia-cusolver-cu11 \
  nvidia-curand-cu11 \
  nvidia-cufft-cu11 \
  nvidia-nvtx-cu11

# ---- 5) install DGL cu117 wheel ----
echo "[install.sh] Installing DGL CUDA 11.7 wheel..."
"${VENV_PIP}" install -U -f https://data.dgl.ai/wheels/cu117/repo.html \
  "dgl==1.1.3+cu117"

# ---- 5.1) small missing runtime dep (you hit this) ----
echo "[install.sh] Installing packaging (DGL runtime dependency)..."
"${VENV_PIP}" install -U packaging

# ---- 6) LD_LIBRARY_PATH helper (hardening) ----
echo "[install.sh] Writing /etc/profile.d/nvidia-pip-libs.sh (LD_LIBRARY_PATH helper)..."
cat >/etc/profile.d/nvidia-pip-libs.sh <<'EOS'
# Add NVIDIA pip-provided CUDA libs to LD_LIBRARY_PATH
# (Needed for wheels built against CUDA 11 when system has CUDA 12+)
export LD_LIBRARY_PATH="$(
python - <<'PY'
import site, glob, os
paths=[]
for sp in site.getsitepackages():
    paths += glob.glob(os.path.join(sp, "nvidia", "*", "lib"))
print(":".join(paths))
PY
):${LD_LIBRARY_PATH:-}"
EOS
chmod +x /etc/profile.d/nvidia-pip-libs.sh

# ---- 7) Verification snippet ----
echo "[install.sh] Verifying torch/dgl CUDA functionality..."
bash -lc "source /etc/profile.d/nvidia-pip-libs.sh && \
  DGLBACKEND=pytorch ${VENV_PY} - <<'PY'
import torch
print('torch:', torch.__version__)
print('cuda available:', torch.cuda.is_available(), 'cuda:', torch.version.cuda)
assert torch.cuda.is_available(), 'torch.cuda.is_available() is False'

import dgl
print('dgl:', dgl.__version__)
g = dgl.rand_graph(10, 20).to('cuda')
src, dst = g.edges()
print('DGL edges() OK on:', src.device, dst.device)
assert str(src.device).startswith('cuda'), 'DGL edges not on CUDA'
print('✅ GPU stack OK')
PY"

echo "[install.sh] ✅ RFdiffusion GPU stack pinned & verified."