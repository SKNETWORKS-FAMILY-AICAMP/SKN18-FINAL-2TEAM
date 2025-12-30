#!/usr/bin/env bash
# ==========================================================
# Unified install:
#  - TORCH venv: RFdiffusion GPU stack (torch cu117 + dgl cu117)
#  - JAX  venv: colabdesign + jax[cuda12] (for designability_test)
#  - includes venv bootstrap + key deps for RFdiffusion
# ==========================================================
set -euo pipefail

echo "[install.sh] start"

# ---------------------------
# Config (env override)
# ---------------------------
VENV_TORCH="${VENV_TORCH:-/opt/venv_torch}"
VENV_JAX="${VENV_JAX:-/opt/venv_jax}"

TORCH_PY="${VENV_TORCH}/bin/python"
TORCH_PIP="${VENV_TORCH}/bin/pip"
JAX_PY="${VENV_JAX}/bin/python"
JAX_PIP="${VENV_JAX}/bin/pip"

# Torch/DGL pinned (cu117)
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu117}"
TORCH_VER="${TORCH_VER:-2.0.1+cu117}"
TORCHVISION_VER="${TORCHVISION_VER:-0.15.2+cu117}"
TORCHAUDIO_VER="${TORCHAUDIO_VER:-2.0.2+cu117}"
DGL_WHEEL_REPO="${DGL_WHEEL_REPO:-https://data.dgl.ai/wheels/cu117/repo.html}"
DGL_VER="${DGL_VER:-1.1.3+cu117}"
NUMPY_VER="${NUMPY_VER:-1.26.4}"

# JAX (cuda12 wheels)
JAX_VER="${JAX_VER:-0.4.28}"  # 필요하면 환경변수로 바꿔도 됨
JAX_WHEEL_URL="${JAX_WHEEL_URL:-https://storage.googleapis.com/jax-releases/jax_cuda_releases.html}"

# Project paths (if available)
RFD_DIR="${RFD_DIR:-/app/RFdiffusion}"

export DEBIAN_FRONTEND=noninteractive

# ---------------------------
# System deps
# ---------------------------
echo "[install.sh] installing system deps..."
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl wget git aria2 unzip \
  python3 python3-venv python3-pip python3-setuptools python3-wheel \
  && rm -rf /var/lib/apt/lists/*

python3 --version

# ---------------------------
# Create venvs if missing
# ---------------------------
bootstrap_venv () {
  local venv_root="$1"
  if [[ ! -x "${venv_root}/bin/python" ]]; then
    echo "[install.sh] venv not found -> creating: ${venv_root}"
    python3 -m venv "${venv_root}"
  fi
  "${venv_root}/bin/pip" install -U pip
}

echo "[install.sh] bootstrap venvs"
bootstrap_venv "${VENV_TORCH}"
bootstrap_venv "${VENV_JAX}"

echo "[install.sh] TORCH_PY=${TORCH_PY}"
echo "[install.sh] JAX_PY=${JAX_PY}"

# ---------------------------
# TORCH venv: GPU stack + RFdiffusion deps
# ---------------------------
echo "[install.sh] [TORCH] clean conflicting pkgs"
"${TORCH_PIP}" uninstall -y dgl torch torchvision torchaudio || true

echo "[install.sh] [TORCH] pin numpy"
"${TORCH_PIP}" install -U "numpy==${NUMPY_VER}"

echo "[install.sh] [TORCH] install torch stack"
"${TORCH_PIP}" install --index-url "${TORCH_INDEX_URL}" \
  "torch==${TORCH_VER}" "torchvision==${TORCHVISION_VER}" "torchaudio==${TORCHAUDIO_VER}"

echo "[install.sh] [TORCH] install pip-provided CUDA11 runtime libs (for cu117 wheels on cuda12 hosts)"
"${TORCH_PIP}" install -U \
  nvidia-cuda-runtime-cu11 \
  nvidia-cublas-cu11 \
  nvidia-cusparse-cu11 \
  nvidia-cusolver-cu11 \
  nvidia-curand-cu11 \
  nvidia-cufft-cu11 \
  nvidia-nvtx-cu11

echo "[install.sh] [TORCH] install DGL cu117 wheel"
"${TORCH_PIP}" install -U -f "${DGL_WHEEL_REPO}" "dgl==${DGL_VER}"

echo "[install.sh] [TORCH] install common runtime deps"
"${TORCH_PIP}" install -U \
  packaging \
  omegaconf hydra-core \
  pyyaml \
  opt_einsum opt_einsum_fx \
  scipy pandas matplotlib tqdm biopython \
  einops \
  "e3nn==0.5.5"

# SE3Transformer: RFdiffusion이 요구 (repo에 포함되어 있으면 그걸 설치)
if [[ -d "${RFD_DIR}/env/SE3Transformer" ]]; then
  echo "[install.sh] [TORCH] install SE3Transformer from ${RFD_DIR}/env/SE3Transformer"
  "${TORCH_PIP}" install -U "${RFD_DIR}/env/SE3Transformer"
else
  echo "[install.sh] [TORCH] NOTE: ${RFD_DIR}/env/SE3Transformer not found. (RFdiffusion repo 구조를 확인 필요)"
fi

# (선택) RFdiffusion requirements가 있으면 설치
if [[ -f "${RFD_DIR}/requirements.txt" ]]; then
  echo "[install.sh] [TORCH] install RFdiffusion requirements.txt"
  "${TORCH_PIP}" install -U -r "${RFD_DIR}/requirements.txt"
fi

# ---------------------------
# LD_LIBRARY_PATH helper (hardening)
# ---------------------------
echo "[install.sh] writing /etc/profile.d/nvidia-pip-libs.sh"
cat >/etc/profile.d/nvidia-pip-libs.sh <<'EOS'
# Add NVIDIA pip-provided CUDA libs to LD_LIBRARY_PATH
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

# ---------------------------
# Verify TORCH/DGL GPU
# ---------------------------
echo "[install.sh] verify torch/dgl cuda"
bash -lc "source /etc/profile.d/nvidia-pip-libs.sh && \
  DGLBACKEND=pytorch ${TORCH_PY} - <<'PY'
import torch
print('torch:', torch.__version__)
print('cuda available:', torch.cuda.is_available(), 'cuda:', torch.version.cuda)
assert torch.cuda.is_available(), 'torch.cuda.is_available() is False'

import dgl
print('dgl:', dgl.__version__)
g = dgl.rand_graph(10, 20).to('cuda')
src, dst = g.edges()
print('DGL edges() OK on:', src.device, dst.device)
assert str(src.device).startswith('cuda')
print('✅ TORCH GPU stack OK')
PY"

# ---------------------------
# JAX venv: colabdesign + jax cuda12
# ---------------------------
echo "[install.sh] [JAX] install colabdesign + jax[cuda12]"
"${JAX_PIP}" install -U packaging

# colabdesign
"${JAX_PIP}" install -U colabdesign

# jax cuda12 (버전이 안 맞으면 JAX_VER 바꿔서 재시도)
"${JAX_PIP}" uninstall -y jax jaxlib || true
"${JAX_PIP}" install -U "jax==${JAX_VER}" -f "${JAX_WHEEL_URL}"
"${JAX_PIP}" install -U "jax[cuda12]==${JAX_VER}" -f "${JAX_WHEEL_URL}"

echo "[install.sh] [JAX] sanity"
"${JAX_PY}" - <<'PY' || true
import jax
print("jax:", jax.__version__)
print("devices:", jax.devices())
PY

echo "[install.sh] done"
echo "[install.sh] venv paths:"
echo "  TORCH_PY=${TORCH_PY}"
echo "  JAX_PY=${JAX_PY}"