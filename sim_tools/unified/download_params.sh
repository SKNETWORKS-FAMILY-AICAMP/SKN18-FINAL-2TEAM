#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/models}"
mkdir -p "${MODELS_DIR}"

echo "[download_params] MODELS_DIR=${MODELS_DIR}"

command -v aria2c >/dev/null 2>&1 || { echo "aria2c not found"; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "tar not found"; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo "unzip not found"; exit 1; }

# -------------------------
# 1) RFdiffusion weights + schedules
# -------------------------
RF_DIR="${MODELS_DIR}/rfdiffusion"
mkdir -p "${RF_DIR}"

BASE_CKPT="${RF_DIR}/Base_ckpt.pt"
COMPLEX_CKPT="${RF_DIR}/Complex_base_ckpt.pt"
SCHEDULES_DIR="${RF_DIR}/schedules"

if [[ ! -f "${BASE_CKPT}" || ! -f "${COMPLEX_CKPT}" || ! -d "${SCHEDULES_DIR}" ]]; then
  echo "[download_params] Downloading RFdiffusion weights/schedules..."
  aria2c -q -x 16 -d "${RF_DIR}" -o schedules.zip "https://files.ipd.uw.edu/krypton/schedules.zip"
  aria2c -q -x 16 -d "${RF_DIR}" -o Base_ckpt.pt "http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
  aria2c -q -x 16 -d "${RF_DIR}" -o Complex_base_ckpt.pt "http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt"

  mkdir -p "${SCHEDULES_DIR}"
  unzip -q "${RF_DIR}/schedules.zip" -d "${SCHEDULES_DIR}"
  rm -f "${RF_DIR}/schedules.zip"
else
  echo "[download_params] RFdiffusion params already exist. skip."
fi

# -------------------------
# 2) AlphaFold params (크다!)
# -------------------------
AF_DIR="${MODELS_DIR}/alphafold"
AF_DONE="${AF_DIR}/done.txt"
mkdir -p "${AF_DIR}"

if [[ ! -f "${AF_DONE}" ]]; then
  echo "[download_params] Downloading AlphaFold params (large)..."
  TMP_TAR="${AF_DIR}/alphafold_params_2022-12-06.tar"
  aria2c -q -x 16 -d "${AF_DIR}" -o alphafold_params_2022-12-06.tar \
    "https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar"
  tar -xf "${TMP_TAR}" -C "${AF_DIR}"
  rm -f "${TMP_TAR}"
  touch "${AF_DONE}"
else
  echo "[download_params] AlphaFold params already exist. skip."
fi

echo "[download_params] done."