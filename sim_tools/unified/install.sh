#!/usr/bin/env bash
set -euo pipefail

echo "[install.sh] start"

# ---------------------------
# Config (env override 가능)
# ---------------------------
MODELS_DIR="${MODELS_DIR:-/models}"
AF_DIR="${AF_DIR:-${MODELS_DIR}/alphafold}"
RFD_DIR="${RFD_DIR:-/app/RFdiffusion}"

VENV_TORCH="${VENV_TORCH:-/opt/venv_torch}"
VENV_JAX="${VENV_JAX:-/opt/venv_jax}"

# Pinned versions (reproducibility)
TORCH_VER="${TORCH_VER:-2.4.0}"
TORCHVISION_VER="${TORCHVISION_VER:-0.19.0}"
TORCHAUDIO_VER="${TORCHAUDIO_VER:-2.4.0}"
CUDA_TAG="${CUDA_TAG:-cu124}"

JAX_VER="${JAX_VER:-0.8.2}"

# ✅ DGL은 2.x(GraphBolt) 이슈 때문에 1.1.3으로 고정 권장
DGL_VER="${DGL_VER:-1.1.3}"

# ---------------------------
# Helpers
# ---------------------------
make_af_symlinks () {
  local dir="${1}"
  mkdir -p "${dir}"
  pushd "${dir}" >/dev/null

  for i in 1 2 3 4 5; do
    [[ -f "params_model_${i}_ptm.npz" ]] && ln -sf "params_model_${i}_ptm.npz" "model_${i}_ptm.npz"
    [[ -f "params_model_${i}.npz" ]] && ln -sf "params_model_${i}.npz" "model_${i}.npz"
    [[ -f "params_model_${i}_multimer_v3.npz" ]] && ln -sf "params_model_${i}_multimer_v3.npz" "model_${i}_multimer_v3.npz"
  done

  popd >/dev/null
}

# ---------------------------
# System deps
# ---------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git wget curl aria2 unzip ca-certificates python3-venv \
  && rm -rf /var/lib/apt/lists/*

python3 --version

# ---------------------------
# Create venvs
# ---------------------------
echo "[install.sh] Creating venvs:"
echo "  - TORCH: ${VENV_TORCH}"
echo "  - JAX  : ${VENV_JAX}"

python3 -m venv "${VENV_TORCH}"
python3 -m venv "${VENV_JAX}"

TORCH_PY="${VENV_TORCH}/bin/python"
TORCH_PIP="${VENV_TORCH}/bin/pip"
JAX_PY="${VENV_JAX}/bin/python"
JAX_PIP="${VENV_JAX}/bin/pip"

"${TORCH_PIP}" install -U pip
"${JAX_PIP}" install -U pip

# ---------------------------
# Common python libs
# ---------------------------
COMMON_PKGS=(
  jedi omegaconf hydra-core icecream pyrsistent decorator pyyaml
  scipy pandas matplotlib tqdm biopython opt_einsum
)

echo "[install.sh] Installing common python deps in both venvs"
"${TORCH_PIP}" install -U "${COMMON_PKGS[@]}"
"${JAX_PIP}"   install -U "${COMMON_PKGS[@]}"

# NVML optional
"${TORCH_PIP}" install -U nvidia-ml-py || true
"${JAX_PIP}"   install -U nvidia-ml-py || true

# ---------------------------
# TORCH venv: RFdiffusion + torch stack
# ---------------------------
echo "[install.sh] [TORCH] Installing torch ${TORCH_VER}+${CUDA_TAG} (pinned)"
"${TORCH_PIP}" install --index-url "https://download.pytorch.org/whl/${CUDA_TAG}" \
  "torch==${TORCH_VER}" "torchvision==${TORCHVISION_VER}" "torchaudio==${TORCHAUDIO_VER}"

echo "[install.sh] [TORCH] Installing RFdiffusion deps"
"${TORCH_PIP}" install -U "pydantic>=2"
"${TORCH_PIP}" install -U e3nn==0.5.5 opt_einsum_fx

# ✅ DGL: GraphBolt 이슈 회피를 위해 1.1.3 고정
echo "[install.sh] [TORCH] Installing DGL==${DGL_VER} (avoid GraphBolt issues)"
"${TORCH_PIP}" uninstall -y dgl || true
"${TORCH_PIP}" install -f "https://data.dgl.ai/wheels/repo.html" "dgl==${DGL_VER}"

# RFdiffusion repo (이미 이미지에 있으면 스킵)
if [[ ! -d "${RFD_DIR}" ]]; then
  echo "[install.sh] [TORCH] Cloning RFdiffusion -> ${RFD_DIR}"
  git clone https://github.com/RosettaCommons/RFdiffusion.git "${RFD_DIR}"
fi

echo "[install.sh] [TORCH] Installing SE3Transformer"
"${TORCH_PIP}" install -U "${RFD_DIR}/env/SE3Transformer"

# ---------------------------
# JAX venv: AlphaFold(ColabDesign) + JAX GPU
# ---------------------------
echo "[install.sh] [JAX] Installing colabdesign"
"${JAX_PIP}" install -U colabdesign

echo "[install.sh] [JAX] Installing GPU JAX (cuda12) pinned=${JAX_VER}"
"${JAX_PIP}" uninstall -y jax jaxlib || true
"${JAX_PIP}" install -U "jax==${JAX_VER}" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
"${JAX_PIP}" install -U "jax[cuda12]==${JAX_VER}" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

# ---------------------------
# AlphaFold params symlink
# ---------------------------
if [[ -f "${AF_DIR}/params_model_1_ptm.npz" ]]; then
  echo "[install.sh] AlphaFold params found. Creating symlinks..."
  make_af_symlinks "${AF_DIR}"
else
  echo "[install.sh] NOTE: ${AF_DIR}/params_model_1_ptm.npz not found yet."
fi

# ---------------------------
# Sanity checks
# ---------------------------
echo "[install.sh] [TORCH] sanity"
"${TORCH_PY}" - <<'PY' || true
import os
import torch
print("torch:", torch.__version__)
print("torch.cuda.is_available:", torch.cuda.is_available())
if torch.cuda.is_available():
  print("torch cuda device:", torch.cuda.get_device_name(0))

os.environ.setdefault("DGLBACKEND","pytorch")
import dgl
print("dgl:", dgl.__version__)
PY

echo "[install.sh] [JAX] sanity"
"${JAX_PY}" - <<'PY' || true
import jax
print("jax:", jax.__version__)
print("jax devices:", jax.devices())
PY

echo "[install.sh] done"
echo "[install.sh] venv paths:"
echo "  TORCH_PY=${TORCH_PY}"
echo "  JAX_PY=${JAX_PY}"