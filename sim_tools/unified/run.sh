#!/usr/bin/env bash
set -euo pipefail

# ====== config (env override 가능) ======
MODELS_DIR="${MODELS_DIR:-/models}"
OUTPUTS_DIR="${OUTPUTS_DIR:-/outputs}"

echo "[run.sh] MODELS_DIR=${MODELS_DIR}"
echo "[run.sh] OUTPUTS_DIR=${OUTPUTS_DIR}"

mkdir -p "${MODELS_DIR}" "${OUTPUTS_DIR}"

# (권장) DGL backend 경고 제거
export DGLBACKEND="${DGLBACKEND:-pytorch}"

# ====== ensure params downloaded ======
if [ -x "/app/download_params.sh" ]; then
  bash /app/download_params.sh
elif [ -f "/app/download_params.sh" ]; then
  bash /app/download_params.sh
else
  echo "[run.sh] ERROR: /app/download_params.sh not found"
  exit 1
fi

# ====== run main pipeline ======
# NOTE: /app/src/main.py 는 install.sh에서 /workspace/unified -> /app symlink로 연결됨
python3 /app/src/main.py "$@"