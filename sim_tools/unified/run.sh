#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/models}"
OUTPUTS_DIR="${OUTPUTS_DIR:-/outputs}"
SCRIPT_DIR="${SCRIPT_DIR:-/workspace/unified}"
RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"
TORCH_VENV="${TORCH_VENV:-/opt/venv_torch}"

export MODELS_DIR OUTPUTS_DIR RFDIFFUSION_DIR TORCH_VENV

echo "[run.sh] MODELS_DIR=$MODELS_DIR"
echo "[run.sh] OUTPUTS_DIR=$OUTPUTS_DIR"
echo "[run.sh] SCRIPT_DIR=$SCRIPT_DIR"
echo "[run.sh] RFDIFFUSION_DIR=$RFDIFFUSION_DIR"

# DGL 관련 런타임 환경변수 (GraphBolt 이슈 회피)
export DGLBACKEND="${DGLBACKEND:-pytorch}"
export DGL_DISABLE_GRAPHBOLT="${DGL_DISABLE_GRAPHBOLT:-1}"
echo "[run.sh] DGLBACKEND=$DGLBACKEND"
echo "[run.sh] DGL_DISABLE_GRAPHBOLT=$DGL_DISABLE_GRAPHBOLT"

# RFdiffusion import 안정화(혹시 editable install이 깨졌을 때도 대비)
export PYTHONPATH="$RFDIFFUSION_DIR:${PYTHONPATH:-}"
echo "[run.sh] PYTHONPATH=$PYTHONPATH"

# NVIDIA libs (torch wheel에 포함된 nvidia/*/lib 경로)
export LD_LIBRARY_PATH="$TORCH_VENV/lib/python3.10/site-packages/nvidia/nvtx/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/nvjitlink/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/nccl/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/curand/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cufft/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cuda_cupti/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cublas/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cusparse/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cudnn/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cusolver/lib:${LD_LIBRARY_PATH:-}"
echo "[run.sh] LD_LIBRARY_PATH=$LD_LIBRARY_PATH"

mkdir -p "$MODELS_DIR" "$OUTPUTS_DIR"

# checks / downloads
bash "$SCRIPT_DIR/download_params.sh"

# RUN
"$TORCH_VENV/bin/python" "$SCRIPT_DIR/src/main.py" "$@"