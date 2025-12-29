# =========================
# RFdiffusion GPU stack pin
# torch (cu117) + dgl (cu117) + numpy (1.26.x) + nvidia-cu11 runtime libs
# =========================

set -euo pipefail

VENV_PY="${VENV_PY:-/opt/venv_torch/bin/python}"
VENV_PIP="${VENV_PIP:-/opt/venv_torch/bin/pip}"

echo "[install.sh] Using python: ${VENV_PY}"
echo "[install.sh] Using pip   : ${VENV_PIP}"

# 0) sanity
"${VENV_PY}" -V
"${VENV_PIP}" -V

# 1) clean conflicting installs (safe to ignore failures)
echo "[install.sh] Removing potentially conflicting packages..."
"${VENV_PIP}" uninstall -y dgl torch torchvision torchaudio || true

# 2) pin numpy first (avoid numpy 2.x breakage with older compiled wheels)
echo "[install.sh] Pinning NumPy..."
"${VENV_PIP}" install -U "numpy==1.26.4"

# 3) install PyTorch cu117 pinned versions (from official PyTorch cu117 index)
echo "[install.sh] Installing PyTorch CUDA 11.7 stack..."
"${VENV_PIP}" install --index-url https://download.pytorch.org/whl/cu117 \
  "torch==2.0.1+cu117" \
  "torchvision==0.15.2+cu117" \
  "torchaudio==2.0.2+cu117"

# 4) install NVIDIA CUDA 11 runtime libs via pip (provides libcusparse.so.11 etc.)
#    -> needed because host CUDA is 12.x (driver OK), but DGL cu117 expects some cu11 libs.
echo "[install.sh] Installing NVIDIA cu11 runtime libs (pip)..."
"${VENV_PIP}" install -U \
  nvidia-cuda-runtime-cu11 \
  nvidia-cublas-cu11 \
  nvidia-cusparse-cu11 \
  nvidia-cusolver-cu11 \
  nvidia-curand-cu11 \
  nvidia-cufft-cu11 \
  nvidia-nvtx-cu11

# 5) install DGL cu117 wheel (from DGL wheel repo)
echo "[install.sh] Installing DGL CUDA 11.7 wheel..."
"${VENV_PIP}" install -U -f https://data.dgl.ai/wheels/cu117/repo.html \
  "dgl==1.1.3+cu117"

# 6) (optional but recommended) ensure LD_LIBRARY_PATH includes pip nvidia lib dirs
#    We'll create a small profile script so login shells can pick it up.
#    run.sh에서도 export하니 이건 "재발 방지용" 하드닝.
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

# 7) Verification snippet (fail fast if GPU path is broken)
echo "[install.sh] Verifying torch/dgl CUDA functionality..."
# Use a subshell so LD_LIBRARY_PATH is applied even during docker build
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