#!/usr/bin/env bash
set -euo pipefail

echo "[install.sh] start (python 3.12 rebuild)"

# ===== Config =====
PY_VER="${PY_VER:-3.12}"

TORCH_VENV="${TORCH_VENV:-/opt/venv_torch}"
TORCH_PY="${TORCH_PY:-${TORCH_VENV}/bin/python}"
TORCH_PIP="${TORCH_PIP:-${TORCH_VENV}/bin/pip}"

# RFdiffusion repo 위치
RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"
RFDIFFUSION_REPO="${RFDIFFUSION_REPO:-https://github.com/RosettaCommons/RFdiffusion.git}"

echo "[install.sh] PY_VER=${PY_VER}"
echo "[install.sh] TORCH_VENV=${TORCH_VENV}"
echo "[install.sh] RFDIFFUSION_DIR=${RFDIFFUSION_DIR}"

# ===== 0) system deps + python3.12 =====
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl git wget unzip \
  software-properties-common \
  build-essential \
  python3-venv python3-pip \
  && rm -rf /var/lib/apt/lists/*

# deadsnakes로 python3.12 설치 (ubuntu 22.04 기준)
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -y
apt-get install -y --no-install-recommends \
  "python${PY_VER}" "python${PY_VER}-venv" "python${PY_VER}-distutils" \
  && rm -rf /var/lib/apt/lists/*

PY_BIN="/usr/bin/python${PY_VER}"
"${PY_BIN}" -V

# ===== 1) create venv (torch) =====
if [[ ! -x "${TORCH_PY}" ]]; then
  echo "[install.sh] creating torch venv: ${TORCH_VENV}"
  "${PY_BIN}" -m venv "${TORCH_VENV}"
fi

"${TORCH_PIP}" install -U pip setuptools wheel

# ===== 2) RFdiffusion repo clone (source code needed for run_inference.py) =====
if [[ ! -d "${RFDIFFUSION_DIR}/.git" ]]; then
  echo "[install.sh] cloning RFdiffusion -> ${RFDIFFUSION_DIR}"
  rm -rf "${RFDIFFUSION_DIR}" || true
  git clone --depth 1 "${RFDIFFUSION_REPO}" "${RFDIFFUSION_DIR}"
else
  echo "[install.sh] RFdiffusion already exists: ${RFDIFFUSION_DIR}"
fi

# ===== 3) Torch + CUDA wheels (Py3.12 호환 필요) =====
# CUDA 12.1 기반 torch wheel을 우선 사용
# (RunPod/대부분 최신 이미지가 CUDA 12 계열이라 호환이 좋음)
echo "[install.sh] installing torch (cu121) ..."
"${TORCH_PIP}" install --index-url https://download.pytorch.org/whl/cu121 \
  torch torchvision torchaudio

# ===== 4) numpy pin (안정성) =====
echo "[install.sh] pin numpy < 2 (safer for many compiled deps)"
"${TORCH_PIP}" install -U "numpy<2"

# ===== 5) NVIDIA pip runtime libs (LD_LIBRARY_PATH로 잡아줄 것) =====
# (환경에 따라 cu12 런타임 패키지 명이 달라질 수 있어, 설치 실패해도 진행하도록)
echo "[install.sh] installing NVIDIA runtime libs (best-effort)"
"${TORCH_PIP}" install -U \
  nvidia-cuda-runtime-cu12 \
  nvidia-cublas-cu12 \
  nvidia-cusparse-cu12 \
  nvidia-cusolver-cu12 \
  nvidia-curand-cu12 \
  nvidia-cufft-cu12 \
  nvidia-nvtx-cu12 \
  || true

# ===== 6) DGL (가능하면 CUDA wheel, 안 되면 기본 dgl) =====
# DGL은 wheel repo를 따로 쓰는 경우가 많아서 best-effort로 처리
# (예: cu121 repo 같은 링크가 존재)  [oai_citation:1‡GitHub](https://github.com/dmlc/dgl/issues/7433?utm_source=chatgpt.com)
echo "[install.sh] installing DGL (best-effort)"
"${TORCH_PIP}" install -U packaging

if "${TORCH_PIP}" install -U -f https://data.dgl.ai/wheels/cu121/repo.html dgl; then
  echo "[install.sh] DGL installed from cu121 wheel repo"
else
  echo "[install.sh] fallback: installing dgl from PyPI (may be CPU-only)"
  "${TORCH_PIP}" install -U dgl
fi

# ===== 7) RFdiffusion python deps (최소 런타임) =====
echo "[install.sh] installing RFdiffusion runtime deps"
"${TORCH_PIP}" install -U \
  omegaconf hydra-core pyyaml \
  opt_einsum opt_einsum_fx \
  einops biopython \
  "e3nn==0.5.5" \
  tqdm scipy

# ===== 8) LD_LIBRARY_PATH helper (venv-aware) =====
echo "[install.sh] writing /etc/profile.d/nvidia-pip-libs.sh"
cat >/etc/profile.d/nvidia-pip-libs.sh <<'EOS'
# Add NVIDIA pip-provided CUDA libs to LD_LIBRARY_PATH (venv-aware)
# This makes libcusparse.so.* etc discoverable at runtime.
VENV_PY="${TORCH_PY:-/opt/venv_torch/bin/python}"
export LD_LIBRARY_PATH="$(
${VENV_PY} - <<'PY'
import site, glob, os
paths=[]
for sp in site.getsitepackages():
    paths += glob.glob(os.path.join(sp, "nvidia", "*", "lib"))
print(":".join(paths))
PY
):${LD_LIBRARY_PATH:-}"
EOS
chmod +x /etc/profile.d/nvidia-pip-libs.sh

# ===== 9) quick verify =====
echo "[install.sh] verify torch + dgl import"
bash -lc "source /etc/profile.d/nvidia-pip-libs.sh && \
  ${TORCH_PY} - <<'PY'
import sys
import torch
print('python:', sys.version)
print('torch:', torch.__version__)
print('cuda available:', torch.cuda.is_available())
try:
    import dgl
    print('dgl:', dgl.__version__)
except Exception as e:
    print('dgl import failed:', e)
PY"

echo "[install.sh] done ✅"