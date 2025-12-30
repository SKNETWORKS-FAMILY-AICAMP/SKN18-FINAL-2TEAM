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

mkdir -p "${MODELS_DIR}" "${AF_DIR}" "${RFD_MODELS_DIR}"

# downloader 선택 (aria2 있으면 병렬/재시도 좋음)
DL_BIN=""
if command -v aria2c >/dev/null 2>&1; then
  DL_BIN="aria2c"
elif command -v wget >/dev/null 2>&1; then
  DL_BIN="wget"
else
  echo "[download_params] ERROR: need aria2c or wget" >&2
  exit 1
fi

download_file() {
  local url="$1"
  local out="$2"

  if [[ -f "${out}" ]]; then
    echo "[download_params] exists: ${out}"
    return 0
  fi

  echo "[download_params] downloading: ${out}"
  local tmp="${out}.tmp"

  if [[ "${DL_BIN}" == "aria2c" ]]; then
    # -c: resume, -x/-s: connections, --retry-wait: wait between retries
    aria2c -c -x 8 -s 8 --retry-wait=2 --max-tries=10 \
      -o "$(basename "${tmp}")" -d "$(dirname "${tmp}")" "${url}"
  else
    # wget resume
    wget -O "${tmp}" "${url}"
  fi

  mv -f "${tmp}" "${out}"
}

echo "[download_params] Downloading RFdiffusion checkpoints..."

# ✅ RFdiffusion ckpt들
download_file \
  "http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt" \
  "${RFD_MODELS_DIR}/Base_ckpt.pt"

download_file \
  "http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt" \
  "${RFD_MODELS_DIR}/Complex_base_ckpt.pt"

download_file \
  "http://files.ipd.uw.edu/pub/RFdiffusion/60f09a193fb5e5ccdc4980417708dbab/Complex_Fold_base_ckpt.pt" \
  "${RFD_MODELS_DIR}/Complex_Fold_base_ckpt.pt"

download_file \
  "http://files.ipd.uw.edu/pub/RFdiffusion/74f51cfb8b440f50d70878e05361d8f0/InpaintSeq_ckpt.pt" \
  "${RFD_MODELS_DIR}/InpaintSeq_ckpt.pt"

echo "[download_params] done."
echo "[download_params] RFdiffusion models dir listing:"
ls -alh "${RFD_MODELS_DIR}" || true

# ===== AlphaFold params =====
# 👉 여기 부분은 너희가 “기존 로직 유지” 하기로 했으니까
# 기존 download_params.sh에서 AF params 받는 로직이 이미 있으면
# 아래 블록을 그 로직으로 그대로 두면 됨.
echo "[download_params] (AlphaFold params) NOTE: existing logic 유지/사용"