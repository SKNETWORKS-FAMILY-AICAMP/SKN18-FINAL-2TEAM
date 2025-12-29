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

# ✅ ckpt 경로 확정 (main.py 기본값도 동일)
export RFD_CKPT="${RFD_CKPT:-/app/RFdiffusion/models/Base_ckpt.pt}"

echo "[run.sh] SCRIPT_DIR=${SCRIPT_DIR}"
echo "[run.sh] RFDIFFUSION_DIR=${RFDIFFUSION_DIR}"
echo "[run.sh] PYTHONPATH=${PYTHONPATH}"
echo "[run.sh] DGLBACKEND=${DGLBACKEND}"
echo "[run.sh] DGL_DISABLE_GRAPHBOLT=${DGL_DISABLE_GRAPHBOLT}"
echo "[run.sh] RFD_CKPT=${RFD_CKPT}"

# ✅ (중요) nvidia-* pip 패키지로 설치된 CUDA 라이브러리 경로를 런타임에 잡아줌
#   - dgl/torch가 libcusparse.so.11 같은 걸 못 찾는 문제 방지
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

# ✅ (중요) numpy 버전 바뀌면 RFdiffusion schedules/*.pkl 캐시가 깨질 수 있어서 자동 삭제
#   - "ModuleNotFoundError: numpy._core.numeric" 같은 pickle 로딩 에러 재발 방지
SCHEDULE_DIR="${RFDIFFUSION_DIR}/schedules"
if [ -d "$SCHEDULE_DIR" ]; then
  echo "[run.sh] cleaning old schedule cache (*.pkl) in $SCHEDULE_DIR"
  find "$SCHEDULE_DIR" -maxdepth 1 -type f -name "*.pkl" -delete || true
fi

bash "${SCRIPT_DIR}/download_params.sh"

# venv 분리: main.py는 torch venv로 실행
/opt/venv_torch/bin/python "${SCRIPT_DIR}/src/main.py" "$@"