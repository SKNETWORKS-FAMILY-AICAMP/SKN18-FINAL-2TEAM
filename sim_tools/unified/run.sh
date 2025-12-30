#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/models}"
OUTPUTS_DIR="${OUTPUTS_DIR:-/outputs}"
TORCH_PY="${TORCH_PY:-/opt/venv_torch/bin/python}"

echo "[run.sh] MODELS_DIR=${MODELS_DIR}"
echo "[run.sh] OUTPUTS_DIR=${OUTPUTS_DIR}"
echo "[run.sh] TORCH_PY=${TORCH_PY}"

mkdir -p "${MODELS_DIR}" "${OUTPUTS_DIR}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"
export PYTHONPATH="${RFDIFFUSION_DIR}:${PYTHONPATH:-}"

export DGLBACKEND="${DGLBACKEND:-pytorch}"
export DGL_DISABLE_GRAPHBOLT="${DGL_DISABLE_GRAPHBOLT:-1}"

export RFD_CKPT="${RFD_CKPT:-/app/RFdiffusion/models/Base_ckpt.pt}"

echo "[run.sh] SCRIPT_DIR=${SCRIPT_DIR}"
echo "[run.sh] RFDIFFUSION_DIR=${RFDIFFUSION_DIR}"
echo "[run.sh] PYTHONPATH=${PYTHONPATH}"
echo "[run.sh] DGLBACKEND=${DGLBACKEND}"
echo "[run.sh] DGL_DISABLE_GRAPHBOLT=${DGL_DISABLE_GRAPHBOLT}"
echo "[run.sh] RFD_CKPT=${RFD_CKPT}"

# ✅ LD_LIBRARY_PATH 세팅 (nvidia pip libs)
if [ -f /etc/profile.d/nvidia-pip-libs.sh ]; then
  # shellcheck disable=SC1091
  source /etc/profile.d/nvidia-pip-libs.sh
fi
echo "[run.sh] LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"

bash "${SCRIPT_DIR}/download_params.sh"

"${TORCH_PY}" "${SCRIPT_DIR}/src/main.py" "$@"