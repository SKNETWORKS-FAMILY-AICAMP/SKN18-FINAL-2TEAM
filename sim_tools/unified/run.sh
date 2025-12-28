#!/usr/bin/env bash
set -euo pipefail

export MODELS_DIR="${MODELS_DIR:-/models}"
export OUTPUTS_DIR="${OUTPUTS_DIR:-/outputs}"

mkdir -p "${MODELS_DIR}" "${OUTPUTS_DIR}"

echo "[run.sh] MODELS_DIR=${MODELS_DIR}"
echo "[run.sh] OUTPUTS_DIR=${OUTPUTS_DIR}"

# 1) 모델/파라미터 준비 (없으면 다운, 있으면 스킵)
bash /app/download_params.sh

# 2) RFdiffusion이 기대하는 경로로 링크 맞추기
mkdir -p /app/RFdiffusion/models

# RFdiffusion ckpt 링크
ln -sf "${MODELS_DIR}/rfdiffusion/Base_ckpt.pt" /app/RFdiffusion/models/Base_ckpt.pt
ln -sf "${MODELS_DIR}/rfdiffusion/Complex_base_ckpt.pt" /app/RFdiffusion/models/Complex_base_ckpt.pt

# schedules는 코랩에서 'schedules/' 폴더가 워킹디렉토리에 생기므로 /app/schedules로 맞춰줌
ln -snf "${MODELS_DIR}/rfdiffusion/schedules" /app/schedules

# 3) AlphaFold params는 코랩에서 'params/' 폴더로 접근하므로 /app/params로 맞춰줌
ln -snf "${MODELS_DIR}/alphafold" /app/params

# 4) 실행
python /app/src/main.py "$@"