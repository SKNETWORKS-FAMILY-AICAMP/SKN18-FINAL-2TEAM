#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/models}"
OUTPUTS_DIR="${OUTPUTS_DIR:-/outputs}"

echo "[run.sh] MODELS_DIR=${MODELS_DIR}"
echo "[run.sh] OUTPUTS_DIR=${OUTPUTS_DIR}"

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

# nvidia-* pip libs path
export LD_LIBRARY_PATH="$(
  /opt/venv_torch/bin/python - <<'PY'
import site, glob, os
paths=[]
for sp in site.getsitepackages():
    for p in glob.glob(os.path.join(sp, "nvidia", "*", "lib")):
        paths.append(p)
print(":".join(paths))
PY
):${LD_LIBRARY_PATH:-}"
echo "[run.sh] LD_LIBRARY_PATH=${LD_LIBRARY_PATH}"

# numpy pickle cache cleanup
SCHEDULE_DIR="${RFDIFFUSION_DIR}/schedules"
if [ -d "$SCHEDULE_DIR" ]; then
  echo "[run.sh] cleaning old schedule cache (*.pkl) in $SCHEDULE_DIR"
  find "$SCHEDULE_DIR" -maxdepth 1 -type f -name "*.pkl" -delete || true
fi

bash "${SCRIPT_DIR}/download_params.sh"

# 실행
/opt/venv_torch/bin/python "${SCRIPT_DIR}/src/main.py" "$@"