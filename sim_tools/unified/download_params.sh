#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/models}"
AF_DIR="${AF_DIR:-${MODELS_DIR}/alphafold}"

RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"
RFD_MODELS_DIR="${RFD_MODELS_DIR:-${RFDIFFUSION_DIR}/models}"

echo "[download_params] MODELS_DIR=${MODELS_DIR}"
echo "[download_params] AF_DIR=${AF_DIR}"
echo "[download_params] RFDIFFUSION_DIR=${RFDIFFUSION_DIR}"
echo "[download_params] RFD_MODELS_DIR=${RFD_MODELS_DIR}"

mkdir -p "${MODELS_DIR}" "${AF_DIR}"
mkdir -p "${RFD_MODELS_DIR}"

# ---------------------------
# RFdiffusion checkpoints
# ---------------------------
echo "[download_params] Downloading RFdiffusion checkpoints..."

download_if_missing () {
  local url="$1"
  local out="$2"

  if [[ -f "${out}" ]]; then
    echo "[download_params] exists: ${out}"
    return 0
  fi

  echo "[download_params] downloading: ${out}"
  wget -O "${out}.tmp" "${url}"
  mv "${out}.tmp" "${out}"
}

download_if_missing \
  "http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt" \
  "${RFD_MODELS_DIR}/Base_ckpt.pt"

# (선택) 필요 시 같이 받아두면 나중에 모드 확장에 편함
download_if_missing \
  "http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt" \
  "${RFD_MODELS_DIR}/Complex_base_ckpt.pt"

download_if_missing \
  "http://files.ipd.uw.edu/pub/RFdiffusion/60f09a193fb5e5ccdc4980417708dbab/Complex_Fold_base_ckpt.pt" \
  "${RFD_MODELS_DIR}/Complex_Fold_base_ckpt.pt"

download_if_missing \
  "http://files.ipd.uw.edu/pub/RFdiffusion/74f51cfb8b440f50d70878e05361d8f0/InpaintSeq_ckpt.pt" \
  "${RFD_MODELS_DIR}/InpaintSeq_ckpt.pt"

echo "[download_params] done."
echo "[download_params] RFdiffusion models dir listing:"
ls -alh "${RFD_MODELS_DIR}" || true

# ---------------------------
# AlphaFold params
# ---------------------------
# 여기(AlphaFold params 다운로드)는 너가 기존에 쓰던 로직 유지하면 돼.
# (너 로그에선 잘 받고 있었으니 그대로 두면 됨)
echo "[download_params] (AlphaFold params) NOTE: existing logic 유지/사용"