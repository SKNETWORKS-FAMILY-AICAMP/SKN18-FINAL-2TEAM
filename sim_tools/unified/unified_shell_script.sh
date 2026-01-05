#!/usr/bin/env bash
set -euo pipefail

########################################
# Config (환경변수로 오버라이드 가능)
########################################
PY_BIN="${PY_BIN:-python3}"
TORCH_VENV="${TORCH_VENV:-/opt/venv_torch}"

APP_DIR="${APP_DIR:-/workspace/unified}"
SCRIPT_DIR="${SCRIPT_DIR:-$APP_DIR}"
RFDIFFUSION_DIR="${RFDIFFUSION_DIR:-/app/RFdiffusion}"

MODELS_DIR="${MODELS_DIR:-/models}"
OUTPUTS_DIR="${OUTPUTS_DIR:-${APP_DIR}/outputs}"

PORT="${PORT:-8000}"
UVICORN_LOG="${UVICORN_LOG:-${APP_DIR}/uvicorn_${PORT}.log}"
UVICORN_PID="${UVICORN_PID:-${APP_DIR}/uvicorn_${PORT}.pid}"

# -----------------------------
# (옵션) S3 업로드 관련 env
# -----------------------------
S3_BUCKET="${S3_BUCKET:-}"
S3_BASE="${S3_BASE:-simulations}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"

AWS_S3_BUCKET="${AWS_S3_BUCKET:-}"
AWS_S3_BASE_PATH="${AWS_S3_BASE_PATH:-}"

# -----------------------------
# ColabDesign / AlphaFold params
# -----------------------------
COLABDESIGN_DIR="${COLABDESIGN_DIR:-/workspace/colabdesign}"
AF_DIR="${AF_DIR:-${MODELS_DIR}/alphafold}"
AF_PARAMS_TAR_URL="${AF_PARAMS_TAR_URL:-https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar}"
AF_PARAMS_TAR_NAME="${AF_PARAMS_TAR_NAME:-alphafold_params_2022-12-06.tar}"

# -----------------------------
# (옵션) JAX GPU 사용 시도 토글
#  - 0: CPU jaxlib 유지 (안전)
#  - 1: CUDA jaxlib 설치 "시도" (실패해도 계속 진행)
# -----------------------------
ENABLE_JAX_CUDA="${ENABLE_JAX_CUDA:-0}"

########################################
# Utils
########################################
log() { echo "[ops] $*"; }
die() { echo "[ops][ERROR] $*" >&2; exit 1; }

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "This command requires root (apt-get). Run as root."
  fi
}

ensure_dir() { mkdir -p "$1"; }
venv_python() { echo "${TORCH_VENV}/bin/python"; }

add_env_if_nonempty() {
  local -n _arr="$1"
  local k="$2"
  local v="${3:-}"
  if [[ -n "${v}" ]]; then
    _arr+=("${k}=${v}")
  fi
}

load_aws_env_from_pid1_if_missing() {
  if env | egrep -q '^(AWS_|S3_)'; then
    return 0
  fi

  if [[ -r /proc/1/environ ]]; then
    while IFS= read -r kv; do
      [[ "$kv" == *=* ]] || continue
      export "$kv"
    done < <(tr '\0' '\n' </proc/1/environ | egrep '^(AWS_|S3_)')
  fi
}

refresh_s3_mapping() {
  AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
  if [[ -n "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" ]]; then
    AWS_DEFAULT_REGION="$AWS_REGION"
  fi

  AWS_S3_BUCKET="${AWS_S3_BUCKET:-}"
  AWS_S3_BASE_PATH="${AWS_S3_BASE_PATH:-}"

  if [[ -z "${S3_BUCKET:-}" && -n "${AWS_S3_BUCKET:-}" ]]; then
    S3_BUCKET="${AWS_S3_BUCKET}"
  fi

  if [[ -z "${S3_BASE:-}" && -n "${AWS_S3_BASE_PATH:-}" ]]; then
    S3_BASE="${AWS_S3_BASE_PATH}"
  fi

  S3_BASE="$(echo "${S3_BASE:-simulations}" | sed 's#^/*##; s#/*$##')"
  [[ -n "${S3_BASE:-}" ]] || S3_BASE="simulations"
}

########################################
# Helper: ensure ./params symlink
########################################
ensure_unified_params_link() {
  # ColabDesign이 종종 ./params 를 찾으므로
  # /workspace/unified/params -> /models/alphafold (AF_DIR) 링크를 보장
  local link_path="${APP_DIR}/params"
  if [[ -L "$link_path" || -e "$link_path" ]]; then
    rm -rf "$link_path" || true
  fi
  ln -s "$AF_DIR" "$link_path"
  log "params link ensured: ${link_path} -> ${AF_DIR}"
}

########################################
# Helper: parse --step from args (NEW)
########################################
extract_step_arg() {
  local step=""
  local args=("$@")
  for ((i=0; i<${#args[@]}; i++)); do
    if [[ "${args[$i]}" == "--step" && $((i+1)) -lt ${#args[@]} ]]; then
      step="${args[$((i+1))]}"
      break
    fi
  done
  echo "$step"
}

########################################
# 0) Up (ALL-IN-ONE)
########################################
cmd_up() {
  load_aws_env_from_pid1_if_missing
  refresh_s3_mapping

  log "========================================"
  log "ALL-IN-ONE UP: install -> download-params -> serve"
  log "APP_DIR=$APP_DIR"
  log "SCRIPT_DIR=$SCRIPT_DIR"
  log "OUTPUTS_DIR=$OUTPUTS_DIR"
  log "MODELS_DIR=$MODELS_DIR"
  log "RFDIFFUSION_DIR=$RFDIFFUSION_DIR"
  log "PORT=$PORT"
  log "AF_DIR=$AF_DIR"
  log "COLABDESIGN_DIR=$COLABDESIGN_DIR"
  log "ENABLE_JAX_CUDA=$ENABLE_JAX_CUDA"
  log "S3_BUCKET=${S3_BUCKET:-<empty>}"
  log "S3_BASE=${S3_BASE:-simulations}"
  log "AWS_REGION=${AWS_REGION:-<empty>}"
  log "========================================"

  cmd_install
  cmd_download_params
  cmd_serve

  log "========================================"
  log "ALL DONE ✅"
  log "Health: curl -s http://127.0.0.1:${PORT}/health ; echo"
  log "Logs  : ./unified_shell_script.sh logs:api"
  log "========================================"
}

########################################
# 1) Install
########################################
cmd_install() {
  need_root
  log "install start"
  log "PY_BIN=$PY_BIN"
  log "TORCH_VENV=$TORCH_VENV"
  log "RFDIFFUSION_DIR=$RFDIFFUSION_DIR"
  log "COLABDESIGN_DIR=$COLABDESIGN_DIR"
  log "ENABLE_JAX_CUDA=$ENABLE_JAX_CUDA"

  $PY_BIN --version

  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends \
    build-essential pkg-config ca-certificates curl git unzip wget \
    python3-venv python3-dev

  if [[ ! -x "$(venv_python)" ]]; then
    log "creating venv at $TORCH_VENV"
    $PY_BIN -m venv "$TORCH_VENV"
  fi

  "$(venv_python)" -m pip install -U pip setuptools wheel
  "$(venv_python)" -m pip install "numpy<2"

  # PyTorch CUDA (RFdiffusion)
  "$(venv_python)" -m pip install \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0

  "$(venv_python)" -m pip install \
    -f https://data.dgl.ai/wheels/torch-2.2/cu121/repo.html \
    dgl

  "$(venv_python)" -m pip install -U opt_einsum pyrsistent e3nn

  # API 서버용 패키지 포함
  "$(venv_python)" -m pip install -U fastapi uvicorn

  # S3 업로드용
  "$(venv_python)" -m pip install -U boto3 botocore

  # RFdiffusion clone + install
  if [[ ! -d "$RFDIFFUSION_DIR" ]]; then
    log "Cloning RFdiffusion into $RFDIFFUSION_DIR"
    git clone https://github.com/RosettaCommons/RFdiffusion.git "$RFDIFFUSION_DIR"
  fi

  log "installing se3-transformer"
  if "$(venv_python)" -c "import se3_transformer" >/dev/null 2>&1; then
    log "se3_transformer already importable. Skipping."
  else
    "$(venv_python)" -m pip install -U opt_einsum

    "$(venv_python)" -m pip install -U \
      "git+https://github.com/NVIDIA/DeepLearningExamples.git#subdirectory=DGLPyTorch/DrugDiscovery/SE3Transformer" \
    || true

    if ! "$(venv_python)" -c "import se3_transformer" >/dev/null 2>&1; then
      if [[ -d "$RFDIFFUSION_DIR/env/SE3Transformer" ]]; then
        log "fallback: installing SE3Transformer from $RFDIFFUSION_DIR/env/SE3Transformer"
        pushd "$RFDIFFUSION_DIR/env/SE3Transformer" >/dev/null
        [[ -f requirements.txt ]] && "$(venv_python)" -m pip install -r requirements.txt
        "$(venv_python)" -m pip install .
        popd >/dev/null
      else
        die "cannot install se3-transformer (no fallback dir found)"
      fi
    fi
  fi

  log "installing RFdiffusion requirements (if present)"
  [[ -f "$RFDIFFUSION_DIR/requirements.txt" ]] && "$(venv_python)" -m pip install -r "$RFDIFFUSION_DIR/requirements.txt" || true
  [[ -f "$RFDIFFUSION_DIR/env/requirements.txt" ]] && "$(venv_python)" -m pip install -r "$RFDIFFUSION_DIR/env/requirements.txt" || true

  "$(venv_python)" -m pip install -U omegaconf hydra-core

  log "installing RFdiffusion (editable)"
  pushd "$RFDIFFUSION_DIR" >/dev/null
  "$(venv_python)" -m pip install -e .
  popd >/dev/null

  ########################################
  # ✅ ColabDesign install (ProteinMPNN / AlphaFold)
  ########################################
  if [[ ! -d "$COLABDESIGN_DIR" ]]; then
    log "Cloning ColabDesign into $COLABDESIGN_DIR"
    git clone https://github.com/sokrypton/ColabDesign.git "$COLABDESIGN_DIR"
  fi
  log "installing ColabDesign (editable)"
  "$(venv_python)" -m pip install -e "$COLABDESIGN_DIR"

  # (옵션) JAX CUDA 설치 시도 (best-effort)
  if [[ "$ENABLE_JAX_CUDA" == "1" ]]; then
    log "trying to install CUDA-enabled jaxlib (best-effort; may fail depending on CUDA/driver)"
    "$(venv_python)" -m pip install -U "jax[cuda12]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html || true
  fi

  log "sanity check"
  "$(venv_python)" - <<'PY'
import sys
print("python:", sys.version.split()[0])
try:
  import torch
  print("torch:", torch.__version__, "cuda:", torch.version.cuda, "avail:", torch.cuda.is_available())
except Exception as e:
  print("torch import failed:", e)

try:
  import colabdesign
  print("colabdesign import: OK")
except Exception as e:
  print("colabdesign import failed:", e)

try:
  import jax
  print("jax:", jax.__version__)
  dev = jax.devices()
  print("jax devices:", dev)
  print("has_gpu:", any(getattr(d, "platform", "") == "gpu" for d in dev))
except Exception as e:
  print("jax import/devices failed:", e)
PY

  log "install done"
}

########################################
# 2) Download params
########################################
download_http() {
  local url="$1"
  local out="$2"

  if [[ -s "$out" ]]; then
    log "download_params OK (exists): $out"
    return 0
  fi

  log "download_params GET: $url -> $out"
  if command -v wget >/dev/null 2>&1; then
    wget -O "$out" --tries=5 --waitretry=2 --timeout=30 "$url"
  elif command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 5 --retry-delay 2 -o "$out" "$url"
  else
    die "need wget or curl"
  fi

  [[ -s "$out" ]] || die "downloaded file is empty: $out"
}

cmd_download_params() {
  log "download_params start"
  ensure_dir "$MODELS_DIR"

  ########################################
  # ✅ AlphaFold params (ColabDesign용)
  ########################################
  ensure_dir "$AF_DIR"
  if [[ ! -s "${AF_DIR}/params_model_1_ptm.npz" ]]; then
    log "AlphaFold params missing; downloading..."
    local tar_path="${AF_DIR}/${AF_PARAMS_TAR_NAME}"
    download_http "$AF_PARAMS_TAR_URL" "$tar_path"

    log "Extracting AlphaFold params (tar --no-same-owner --no-same-permissions)"
    # ✅ FIX: tar 실패를 성공 처리하지 않도록 || true 제거
    tar --no-same-owner --no-same-permissions -xf "$tar_path" -C "$AF_DIR"

    # 최소 파일 존재 검사
    if [[ ! -s "${AF_DIR}/params_model_1_ptm.npz" ]]; then
      die "AlphaFold params extraction failed: ${AF_DIR}/params_model_1_ptm.npz not found"
    fi
    log "AlphaFold params ready: ${AF_DIR}"
  else
    log "AlphaFold params OK (exists): ${AF_DIR}/params_model_1_ptm.npz"
  fi

  ########################################
  # RFdiffusion checkpoints (기존 로직 유지)
  ########################################
  RFD_MODELS_DIR="${RFD_MODELS_DIR:-$RFDIFFUSION_DIR/models}"
  ensure_dir "$RFD_MODELS_DIR"

  RFD_SOURCE_DIR="${RFD_SOURCE_DIR:-$MODELS_DIR/rfdiffusion}"
  ensure_dir "$RFD_SOURCE_DIR"

  log "MODELS_DIR=$MODELS_DIR"
  log "AF_DIR=$AF_DIR"
  log "RFDIFFUSION_DIR=$RFDIFFUSION_DIR"
  log "RFD_MODELS_DIR=$RFD_MODELS_DIR"
  log "RFD_SOURCE_DIR=$RFD_SOURCE_DIR"

  stage_from_cache() {
    local name="$1"
    local src="$RFD_SOURCE_DIR/$name"
    local dst="$RFD_MODELS_DIR/$name"
    if [[ -s "$dst" ]]; then
      log "OK (already in target): $dst"
      return 0
    fi
    if [[ -s "$src" ]]; then
      log "STAGE: $src -> $dst"
      cp -f "$src" "$dst"
      return 0
    fi
    return 1
  }

  save_to_cache() {
    local name="$1"
    local src="$RFD_MODELS_DIR/$name"
    local dst="$RFD_SOURCE_DIR/$name"
    if [[ -s "$dst" ]]; then
      log "CACHE OK (exists): $dst"
      return 0
    fi
    if [[ -s "$src" ]]; then
      log "CACHE SAVE: $src -> $dst"
      cp -f "$src" "$dst"
    fi
  }

  BASE_CKPT_URL="http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
  COMPLEX_BASE_URL="http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt"
  COMPLEX_FOLD_BASE_URL="http://files.ipd.uw.edu/pub/RFdiffusion/60f09a193fb5e5ccdc4980417708dbab/Complex_Fold_base_ckpt.pt"
  INPAINTSEQ_URL="http://files.ipd.uw.edu/pub/RFdiffusion/74f51cfb8b440f50d70878e05361d8f0/InpaintSeq_ckpt.pt"

  need_names=("Base_ckpt.pt" "Complex_base_ckpt.pt" "Complex_Fold_base_ckpt.pt" "InpaintSeq_ckpt.pt")
  need_urls=("$BASE_CKPT_URL" "$COMPLEX_BASE_URL" "$COMPLEX_FOLD_BASE_URL" "$INPAINTSEQ_URL")

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

  missing=0
  for name in "${need_names[@]}"; do
    f="$RFD_MODELS_DIR/$name"
    if [[ ! -s "$f" ]]; then
      echo "[download_params][ERROR] missing or empty: $f" >&2
      missing=1
    fi
  done

  log "RFdiffusion models dir listing:"
  ls -lh "$RFD_MODELS_DIR" || true
  log "RFdiffusion cache dir listing:"
  ls -lh "$RFD_SOURCE_DIR" || true

  [[ "$missing" -eq 0 ]] || die "one or more RFdiffusion ckpt downloads failed"
  log "download_params done"
}

########################################
# 3) Run
########################################
cmd_run() {
  load_aws_env_from_pid1_if_missing
  refresh_s3_mapping

  log "run start"
  export MODELS_DIR OUTPUTS_DIR RFDIFFUSION_DIR TORCH_VENV
  export AF_DIR COLABDESIGN_DIR

  log "MODELS_DIR=$MODELS_DIR"
  log "AF_DIR=$AF_DIR"
  log "OUTPUTS_DIR=$OUTPUTS_DIR"
  log "SCRIPT_DIR=$SCRIPT_DIR"
  log "RFDIFFUSION_DIR=$RFDIFFUSION_DIR"

  export DGLBACKEND="${DGLBACKEND:-pytorch}"
  export DGL_DISABLE_GRAPHBOLT="${DGL_DISABLE_GRAPHBOLT:-1}"
  log "DGLBACKEND=$DGLBACKEND"
  log "DGL_DISABLE_GRAPHBOLT=$DGL_DISABLE_GRAPHBOLT"

  export PYTHONPATH="$SCRIPT_DIR/src:$RFDIFFUSION_DIR:${PYTHONPATH:-}"
  log "PYTHONPATH=$PYTHONPATH"

  # ✅ NEW: step별로 LD_LIBRARY_PATH 분기 (JAX가 꼬이는 케이스 방지)
  local step
  step="$(extract_step_arg "$@")"
  log "detected step=${step:-<empty>}"

  if [[ "$step" == "alphafold" || "$step" == "proteinMPNN" ]]; then
    unset LD_LIBRARY_PATH || true
    log "LD_LIBRARY_PATH unset for step=$step (jax/af safety)"
  else
    export LD_LIBRARY_PATH="$TORCH_VENV/lib/python3.10/site-packages/nvidia/nvtx/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/nvjitlink/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/nccl/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/curand/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cufft/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cuda_cupti/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cublas/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cusparse/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cudnn/lib:$TORCH_VENV/lib/python3.10/site-packages/nvidia/cusolver/lib:${LD_LIBRARY_PATH:-}"
    log "LD_LIBRARY_PATH set (torch/rfdiffusion)"
  fi

  if [[ -n "${AWS_REGION:-}" ]]; then
    export AWS_REGION
    export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
  fi
  [[ -n "${AWS_S3_BUCKET:-}" ]] && export AWS_S3_BUCKET
  [[ -n "${AWS_S3_BASE_PATH:-}" ]] && export AWS_S3_BASE_PATH

  [[ -n "${S3_BUCKET:-}" ]] && export S3_BUCKET
  [[ -n "${S3_BASE:-}" ]] && export S3_BASE

  log "S3_BUCKET=${S3_BUCKET:-<empty>}"
  log "S3_BASE=${S3_BASE:-<empty>}"
  log "AWS_REGION=${AWS_REGION:-<empty>}"

  ensure_dir "$MODELS_DIR"
  ensure_dir "$OUTPUTS_DIR"

  cmd_download_params
  ensure_unified_params_link

  cd "$APP_DIR"
  "$(venv_python)" "$SCRIPT_DIR/src/main.py" "$@"
}

########################################
# 4) Serve
########################################
cmd_serve() {
  load_aws_env_from_pid1_if_missing
  refresh_s3_mapping

  log "serve start"
  ensure_dir "$APP_DIR"
  ensure_dir "$OUTPUTS_DIR"

  "$(venv_python)" -c "import uvicorn, fastapi" >/dev/null 2>&1 || \
    "$(venv_python)" -m pip install -U uvicorn fastapi

  if [[ -f "$UVICORN_PID" ]] && ps -p "$(cat "$UVICORN_PID")" >/dev/null 2>&1; then
    log "Already running: PID=$(cat "$UVICORN_PID")"
    exit 0
  fi

  cd "$APP_DIR"
  ensure_unified_params_link

  local env_kv=()
  env_kv+=("SCRIPT_DIR=$SCRIPT_DIR")
  env_kv+=("OPS_SH=$SCRIPT_DIR/unified_shell_script.sh")
  env_kv+=("OUTPUTS_DIR=$OUTPUTS_DIR")
  env_kv+=("TORCH_VENV=$TORCH_VENV")
  env_kv+=("PYTHONPATH=$RFDIFFUSION_DIR")
  env_kv+=("MODELS_DIR=$MODELS_DIR")
  env_kv+=("AF_DIR=$AF_DIR")
  env_kv+=("COLABDESIGN_DIR=$COLABDESIGN_DIR")

  add_env_if_nonempty env_kv "S3_BUCKET" "${S3_BUCKET:-}"
  add_env_if_nonempty env_kv "S3_BASE" "${S3_BASE:-}"

  add_env_if_nonempty env_kv "AWS_REGION" "${AWS_REGION:-}"
  if [[ -n "${AWS_REGION:-}" ]]; then
    add_env_if_nonempty env_kv "AWS_DEFAULT_REGION" "${AWS_DEFAULT_REGION:-$AWS_REGION}"
  else
    add_env_if_nonempty env_kv "AWS_DEFAULT_REGION" "${AWS_DEFAULT_REGION:-}"
  fi

  add_env_if_nonempty env_kv "AWS_S3_BUCKET" "${AWS_S3_BUCKET:-}"
  add_env_if_nonempty env_kv "AWS_S3_BASE_PATH" "${AWS_S3_BASE_PATH:-}"

  add_env_if_nonempty env_kv "AWS_ACCESS_KEY_ID" "${AWS_ACCESS_KEY_ID:-}"
  add_env_if_nonempty env_kv "AWS_SECRET_ACCESS_KEY" "${AWS_SECRET_ACCESS_KEY:-}"
  add_env_if_nonempty env_kv "AWS_SESSION_TOKEN" "${AWS_SESSION_TOKEN:-}"

  nohup env "${env_kv[@]}" \
    "$(venv_python)" -m uvicorn api_server:app --host 0.0.0.0 --port "$PORT" \
    > "$UVICORN_LOG" 2>&1 &

  echo $! > "$UVICORN_PID"
  log "Started: PID=$(cat "$UVICORN_PID"), log=$UVICORN_LOG"
}

cmd_stop() {
  if [[ -f "$UVICORN_PID" ]]; then
    local pid
    pid="$(cat "$UVICORN_PID" || true)"
    if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
      log "Stopping uvicorn PID=$pid"
      kill "$pid" || true
      sleep 0.2 || true
      ps -p "$pid" >/dev/null 2>&1 && kill -9 "$pid" || true
    fi
    rm -f "$UVICORN_PID"
  fi
  log "stop done"
}

cmd_logs_api() { tail -f "$UVICORN_LOG"; }

cmd_logs_job() {
  local name="${1:-}"
  [[ -n "$name" ]] || die "usage: $0 logs:job <job_name>"
  tail -f "${OUTPUTS_DIR}/_logs/${name}.log"
}

usage() {
  cat <<EOF
Usage:
  ./unified_shell_script.sh up
  ./unified_shell_script.sh install
  ./unified_shell_script.sh download-params
  ./unified_shell_script.sh run [args...]
  ./unified_shell_script.sh serve
  ./unified_shell_script.sh stop
  ./unified_shell_script.sh logs:api
  ./unified_shell_script.sh logs:job <job_name>

Env overrides:
  TORCH_VENV=/opt/venv_torch
  APP_DIR=/workspace/unified
  SCRIPT_DIR=/workspace/unified
  OUTPUTS_DIR=/workspace/unified/outputs
  MODELS_DIR=/models
  PORT=8000

AlphaFold/ColabDesign:
  AF_DIR=/models/alphafold
  COLABDESIGN_DIR=/workspace/colabdesign
  ENABLE_JAX_CUDA=0|1

S3 upload env (optional):
  S3_BUCKET=my-bucket
  S3_BASE=simulations
  AWS_REGION=ap-northeast-2
EOF
}

main() {
  local cmd="${1:-up}"
  shift || true

  case "$cmd" in
    up) cmd_up "$@" ;;
    install) cmd_install "$@" ;;
    download-params) cmd_download_params "$@" ;;
    run) cmd_run "$@" ;;
    serve) cmd_serve "$@" ;;
    stop) cmd_stop "$@" ;;
    logs:api) cmd_logs_api ;;
    logs:job) cmd_logs_job "$@" ;;
    help|--help|-h) usage ;;
    *) die "unknown command: $cmd (try: ./unified_shell_script.sh help)" ;;
  esac
}

main "$@"