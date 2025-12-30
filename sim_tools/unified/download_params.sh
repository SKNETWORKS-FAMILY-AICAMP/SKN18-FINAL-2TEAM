#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/models}"

# --- AlphaFold params (유지: 여기서는 "존재/디렉토리 생성"만 하고, 다운로드 로직은 네 기존 방식 그대로 두는 자리) ---
AF_DIR="${AF_DIR:-$MODELS_DIR/alphafold}"
mkdir -p "$AF_DIR"

# --- RFdiffusion ckpt target ---
RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"
RFD_MODELS_DIR="${RFD_MODELS_DIR:-$RFDIFFUSION_DIR/models}"
mkdir -p "$RFD_MODELS_DIR"

# --- (옵션) 볼륨 캐시: 여기에 있으면 다운로드 안 하고 복사만 함 ---
RFD_SOURCE_DIR="${RFD_SOURCE_DIR:-$MODELS_DIR/rfdiffusion}"
mkdir -p "$RFD_SOURCE_DIR"

echo "[download_params] MODELS_DIR=$MODELS_DIR"
echo "[download_params] AF_DIR=$AF_DIR (AlphaFold params: keep existing logic)"
echo "[download_params] RFDIFFUSION_DIR=$RFDIFFUSION_DIR"
echo "[download_params] RFD_MODELS_DIR=$RFD_MODELS_DIR"
echo "[download_params] RFD_SOURCE_DIR=$RFD_SOURCE_DIR"
echo "[download_params] Downloading/Stage RFdiffusion checkpoints..."

# --- download helper (재다운 방지: 파일이 있으면 스킵) ---
download_http() {
  local url="$1"
  local out="$2"

  if [[ -s "$out" ]]; then
    echo "[download_params] OK (exists): $out"
    return 0
  fi

  echo "[download_params] GET: $url -> $out"
  if command -v wget >/dev/null 2>&1; then
    wget -O "$out" --tries=5 --waitretry=2 --timeout=30 "$url"
  elif command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 5 --retry-delay 2 -o "$out" "$url"
  else
    echo "[download_params] ERROR: need wget or curl" >&2
    return 1
  fi

  # sanity: 0바이트면 실패 처리
  if [[ ! -s "$out" ]]; then
    echo "[download_params] ERROR: downloaded file is empty: $out" >&2
    return 1
  fi
}

# --- stage helper: 캐시(/models/rfdiffusion)에 있으면 타겟(/app/RFdiffusion/models)로 복사 ---
stage_from_cache() {
  local name="$1"
  local src="$RFD_SOURCE_DIR/$name"
  local dst="$RFD_MODELS_DIR/$name"

  if [[ -s "$dst" ]]; then
    echo "[download_params] OK (already in target): $dst"
    return 0
  fi

  if [[ -s "$src" ]]; then
    echo "[download_params] STAGE: $src -> $dst"
    cp -f "$src" "$dst"
    return 0
  fi

  return 1
}

# --- cache helper: 다운로드 성공한 파일을 /models/rfdiffusion에도 복사해 다음번 재다운 방지 ---
save_to_cache() {
  local name="$1"
  local src="$RFD_MODELS_DIR/$name"
  local dst="$RFD_SOURCE_DIR/$name"

  if [[ -s "$dst" ]]; then
    echo "[download_params] CACHE OK (exists): $dst"
    return 0
  fi

  if [[ -s "$src" ]]; then
    echo "[download_params] CACHE SAVE: $src -> $dst"
    cp -f "$src" "$dst"
  fi
}

# --- Official-ish public links (RFdiffusion ckpts) ---
# (문서에 나온 파일 서버 링크 그대로 사용)  [oai_citation:1‡ccportal.ims.ac.jp](https://ccportal.ims.ac.jp/en/print/pdf/node/3519)
BASE_CKPT_URL="http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
COMPLEX_BASE_URL="http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt"
COMPLEX_FOLD_BASE_URL="http://files.ipd.uw.edu/pub/RFdiffusion/60f09a193fb5e5ccdc4980417708dbab/Complex_Fold_base_ckpt.pt"
INPAINTSEQ_URL="http://files.ipd.uw.edu/pub/RFdiffusion/74f51cfb8b440f50d70878e05361d8f0/InpaintSeq_ckpt.pt"

need_names=(
  "Base_ckpt.pt"
  "Complex_base_ckpt.pt"
  "Complex_Fold_base_ckpt.pt"
  "InpaintSeq_ckpt.pt"
)

need_urls=(
  "$BASE_CKPT_URL"
  "$COMPLEX_BASE_URL"
  "$COMPLEX_FOLD_BASE_URL"
  "$INPAINTSEQ_URL"
)

# --- main: stage -> download -> verify -> cache ---
for i in "${!need_names[@]}"; do
  name="${need_names[$i]}"
  url="${need_urls[$i]}"
  out="$RFD_MODELS_DIR/$name"

  if stage_from_cache "$name"; then
    continue
  fi

  download_http "$url" "$out"
  save_to_cache "$name"
done

# --- final verification: 하나라도 없으면 종료(요구사항: 다운 실패 시 종료) ---
missing=0
for name in "${need_names[@]}"; do
  f="$RFD_MODELS_DIR/$name"
  if [[ ! -s "$f" ]]; then
    echo "[download_params] ERROR: missing or empty: $f" >&2
    missing=1
  fi
done

echo "[download_params] RFdiffusion models dir listing:"
ls -lh "$RFD_MODELS_DIR" || true
echo "[download_params] RFdiffusion cache dir listing:"
ls -lh "$RFD_SOURCE_DIR" || true

if [[ "$missing" -eq 1 ]]; then
  echo "[download_params] ERROR: one or more RFdiffusion ckpt downloads failed." >&2
  exit 2
fi

echo "[download_params] (AlphaFold params) NOTE: keep existing logic (not changed here)"
echo "[download_params] done."