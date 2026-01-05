#!/usr/bin/env bash
set -euo pipefail

# (옵션) 디버그: OPS_DEBUG=1 이면 bash trace 출력
OPS_DEBUG="${OPS_DEBUG:-0}"
[[ "$OPS_DEBUG" == "1" ]] && set -x

########################################
# Config (환경변수로 오버라이드 가능)
########################################
PY_BIN="${PY_BIN:-python3}"

# ✅ Split venvs
TORCH_VENV="${TORCH_VENV:-/opt/venv_torch}"
JAX_VENV="${JAX_VENV:-/opt/venv_jax}"

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
# ✅ JAX GPU 정책(재발 방지)
#  - 0: CPU jaxlib 허용
#  - 1: CUDA jaxlib "반드시" 성공해야 함 (실패하면 install 단계에서 종료)
# -----------------------------
ENABLE_JAX_CUDA="${ENABLE_JAX_CUDA:-0}"

# -----------------------------
# ✅ (권장) JAX CUDA wheel index
# -----------------------------
JAX_CUDA_WHEEL_INDEX="${JAX_CUDA_WHEEL_INDEX:-https://storage.googleapis.com/jax-releases/jax_cuda_releases.html}"

########################################
# Utils
########################################
log()  { echo "[ops] $*"; }
die()  { echo "[ops][ERROR] $*" >&2; exit 1; }
warn() { echo "[ops][WARN] $*" >&2; }

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "This command requires root (apt-get). Run as root."
  fi
}

ensure_dir() { mkdir -p "$1"; }

venv_python_torch() { echo "${TORCH_VENV}/bin/python"; }
venv_python_jax()   { echo "${JAX_VENV}/bin/python"; }

# -----------------------------
# Runtime helpers (venv-safe)
#  - python 버전(3.10 등) 하드코딩 제거
#  - site-packages 기반으로 nvidia lib 경로 구성
# -----------------------------
torch_site_packages() {
  "$(venv_python_torch)" - <<'PY'
import site
paths = site.getsitepackages()
print(paths[0] if paths else "")
PY
}

jax_site_packages() {
  "$(venv_python_jax)" - <<'PY'
import site
paths = site.getsitepackages()
print(paths[0] if paths else "")
PY
}

set_ld_library_path_for_torch() {
  local sp
  sp="$(torch_site_packages || true)"

  if [[ -z "${sp}" ]]; then
    warn "cannot resolve torch site-packages; LD_LIBRARY_PATH not set"
    return 0
  fi

  local nvr="${sp}/nvidia"
  local parts=()

  for d in \
    "$nvr/nvtx/lib" \
    "$nvr/nvjitlink/lib" \
    "$nvr/nccl/lib" \
    "$nvr/curand/lib" \
    "$nvr/cufft/lib" \
    "$nvr/cuda_runtime/lib" \
    "$nvr/cuda_nvrtc/lib" \
    "$nvr/cuda_cupti/lib" \
    "$nvr/cublas/lib" \
    "$nvr/cusparse/lib" \
    "$nvr/cudnn/lib" \
    "$nvr/cusolver/lib"
  do
    [[ -d "$d" ]] && parts+=("$d")
  done

  if [[ "${#parts[@]}" -eq 0 ]]; then
    warn "no nvidia lib dirs found under: $nvr (LD_LIBRARY_PATH unchanged)"
    return 0
  fi

  export LD_LIBRARY_PATH="$(IFS=:; echo "${parts[*]}"):${LD_LIBRARY_PATH:-}"
}

# ✅ JAX는 torch venv의 nvidia libs로 꼬일 수 있으니 "제거"하되,
#    시스템 CUDA 런타임 경로는 유지/추가(재발 방지).
set_ld_library_path_for_jax() {
  local cur="${LD_LIBRARY_PATH:-}"

  # 1) torch venv 아래 경로가 들어있으면 제거
  if [[ -n "${cur}" ]]; then
    cur="$(echo "$cur" | tr ':' '\n' | grep -vE '^/opt/venv_torch/' | paste -sd ':' -)"
  fi

  # 2) 시스템 CUDA 후보 경로를 앞쪽에 추가
  #    (이미 있으면 중복 없이 유지)
  local candidates=(
    "/usr/local/cuda/lib64"
    "/usr/local/cuda/lib"
    "/usr/lib/x86_64-linux-gnu"
    "/usr/lib64"
  )

  local parts=()
  for d in "${candidates[@]}"; do
    [[ -d "$d" ]] && parts+=("$d")
  done

  local prefix=""
  if [[ "${#parts[@]}" -gt 0 ]]; then
    prefix="$(IFS=:; echo "${parts[*]}")"
  fi

  if [[ -n "$prefix" && -n "$cur" ]]; then
    export LD_LIBRARY_PATH="${prefix}:${cur}"
  elif [[ -n "$prefix" ]]; then
    export LD_LIBRARY_PATH="${prefix}"
  else
    # 시스템 경로를 못 찾으면 cur만 유지 (그래도 unset은 안 함)
    export LD_LIBRARY_PATH="${cur}"
  fi

  log "LD_LIBRARY_PATH(jax)=${LD_LIBRARY_PATH:-<empty>}"
}

sanity_torch() {
  log "sanity(torch): python=$("$(venv_python_torch)" -V 2>&1 | tr -d '\r')"
  if command -v nvidia-smi >/dev/null 2>&1; then
    log "sanity(torch): nvidia-smi OK"
    nvidia-smi -L || true
  else
    warn "sanity(torch): nvidia-smi not found"
  fi

  "$(venv_python_torch)" - <<'PY'
try:
  import torch
  print("[sanity][torch] version:", torch.__version__)
  print("[sanity][torch] cuda:", torch.version.cuda)
  print("[sanity][torch] cuda_available:", torch.cuda.is_available())
  if torch.cuda.is_available():
    print("[sanity][torch] device:", torch.cuda.get_device_name(0))
  try:
    import torch.backends.cudnn as cudnn
    print("[sanity][torch] cudnn_version:", cudnn.version())
  except Exception as e:
    print("[sanity][torch] cudnn check failed:", repr(e))
except Exception as e:
  print("[sanity][torch] import torch failed:", repr(e))
PY
}

# ✅ JAX GPU 강제 체크 함수 (재발 방지)
sanity_jax_and_must_gpu_if_requested() {
  log "sanity(jax): python=$("$(venv_python_jax)" -V 2>&1 | tr -d '\r')"
  "$(venv_python_jax)" - <<'PY'
import os, sys
want_gpu = os.environ.get("ENABLE_JAX_CUDA","0") == "1"
try:
  import jax
  dev = jax.devices()
  has_gpu = any(getattr(d, "platform", "") == "gpu" for d in dev)
  print("[sanity][jax] version:", jax.__version__)
  print("[sanity][jax] devices:", dev)
  print("[sanity][jax] has_gpu:", has_gpu)
  if want_gpu and not has_gpu:
    raise SystemExit("[sanity][jax] ENABLE_JAX_CUDA=1 but has_gpu=False (CUDA jaxlib not active)")
except SystemExit as e:
  print(str(e))
  raise
except Exception as e:
  print("[sanity][jax] import/devices failed:", repr(e))
  raise
PY
}

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
  local link_path="${APP_DIR}/params"
  if [[ -L "$link_path" || -e "$link_path" ]]; then
    rm -rf "$link_path" || true
  fi
  ln -s "$AF_DIR" "$link_path"
  log "params link ensured: ${link_path} -> ${AF_DIR}"
}

########################################
# Helper: parse --step from args
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
  log "TORCH_VENV=$TORCH_VENV"
  log "JAX_VENV=$JAX_VENV"
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
  log "JAX_VENV=$JAX_VENV"
  log "RFDIFFUSION_DIR=$RFDIFFUSION_DIR"
  log "COLABDESIGN_DIR=$COLABDESIGN_DIR"
  log "ENABLE_JAX_CUDA=$ENABLE_JAX_CUDA"

  $PY_BIN --version

  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends \
    build-essential pkg-config ca-certificates curl git unzip wget \
    python3-venv python3-dev

  # ---------- torch venv ----------
  if [[ ! -x "$(venv_python_torch)" ]]; then
    log "creating TORCH venv at $TORCH_VENV"
    $PY_BIN -m venv "$TORCH_VENV"
  fi

  "$(venv_python_torch)" -m pip install -U pip setuptools wheel
  "$(venv_python_torch)" -m pip install "numpy<2"

  # PyTorch CUDA (RFdiffusion)
  "$(venv_python_torch)" -m pip install \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0

  # ✅ cuDNN 재고정
  "$(venv_python_torch)" -m pip install -U --no-deps "nvidia-cudnn-cu12==8.9.2.26" || true

  "$(venv_python_torch)" -m pip install \
    -f https://data.dgl.ai/wheels/torch-2.2/cu121/repo.html \
    dgl

  "$(venv_python_torch)" -m pip install -U opt_einsum pyrsistent e3nn

  # API 서버용 패키지 포함 (torch venv에서 띄움)
  "$(venv_python_torch)" -m pip install -U fastapi uvicorn

  # S3 업로드용
  "$(venv_python_torch)" -m pip install -U boto3 botocore

  # RFdiffusion clone + install
  if [[ ! -d "$RFDIFFUSION_DIR" ]]; then
    log "Cloning RFdiffusion into $RFDIFFUSION_DIR"
    git clone https://github.com/RosettaCommons/RFdiffusion.git "$RFDIFFUSION_DIR"
  fi

  log "installing se3-transformer (TORCH_VENV)"
  if "$(venv_python_torch)" -c "import se3_transformer" >/dev/null 2>&1; then
    log "se3_transformer already importable. Skipping."
  else
    "$(venv_python_torch)" -m pip install -U opt_einsum

    "$(venv_python_torch)" -m pip install -U \
      "git+https://github.com/NVIDIA/DeepLearningExamples.git#subdirectory=DGLPyTorch/DrugDiscovery/SE3Transformer" \
    || true

    if ! "$(venv_python_torch)" -c "import se3_transformer" >/dev/null 2>&1; then
      if [[ -d "$RFDIFFUSION_DIR/env/SE3Transformer" ]]; then
        log "fallback: installing SE3Transformer from $RFDIFFUSION_DIR/env/SE3Transformer"
        pushd "$RFDIFFUSION_DIR/env/SE3Transformer" >/dev/null
        [[ -f requirements.txt ]] && "$(venv_python_torch)" -m pip install -r requirements.txt
        "$(venv_python_torch)" -m pip install .
        popd >/dev/null
      else
        die "cannot install se3-transformer (no fallback dir found)"
      fi
    fi
  fi

  log "installing RFdiffusion requirements (if present) (TORCH_VENV)"
  [[ -f "$RFDIFFUSION_DIR/requirements.txt" ]] && "$(venv_python_torch)" -m pip install -r "$RFDIFFUSION_DIR/requirements.txt" || true
  [[ -f "$RFDIFFUSION_DIR/env/requirements.txt" ]] && "$(venv_python_torch)" -m pip install -r "$RFDIFFUSION_DIR/env/requirements.txt" || true

  "$(venv_python_torch)" -m pip install -U omegaconf hydra-core

  log "installing RFdiffusion (editable) (TORCH_VENV)"
  pushd "$RFDIFFUSION_DIR" >/dev/null
  "$(venv_python_torch)" -m pip install -e .
  popd >/dev/null

  # ---------- jax venv ----------
  if [[ ! -x "$(venv_python_jax)" ]]; then
    log "creating JAX venv at $JAX_VENV"
    $PY_BIN -m venv "$JAX_VENV"
  fi

  "$(venv_python_jax)" -m pip install -U pip setuptools wheel
  "$(venv_python_jax)" -m pip install "numpy<2"
  "$(venv_python_jax)" -m pip install -U boto3 botocore
  "$(venv_python_jax)" -m pip install -U pandas

  ########################################
  # ✅ ColabDesign install (JAX_VENV)
  ########################################
  if [[ ! -d "$COLABDESIGN_DIR" ]]; then
    log "Cloning ColabDesign into $COLABDESIGN_DIR"
    git clone https://github.com/sokrypton/ColabDesign.git "$COLABDESIGN_DIR"
  fi

  log "installing ColabDesign (editable) (JAX_VENV)"
  "$(venv_python_jax)" -m pip install -e "$COLABDESIGN_DIR"

  ########################################
  # ✅ JAX CUDA: 재발 방지 설치 로직
  ########################################
  if [[ "$ENABLE_JAX_CUDA" == "1" ]]; then
    log "JAX CUDA REQUIRED: removing CPU jax/jaxlib then installing CUDA-enabled jaxlib (JAX_VENV)"
    # 1) 먼저 기존 jax/jaxlib 제거 (CPU 잔재가 남으면 계속 CPU로 뜨는 케이스 방지)
    "$(venv_python_jax)" -m pip uninstall -y jax jaxlib || true

    # 2) CUDA jax 설치 (실패하면 바로 죽어야 재발 방지 됨)
    #    (여기서 || true 절대 금지)
    "$(venv_python_jax)" -m pip install -U "jax[cuda12]" -f "$JAX_CUDA_WHEEL_INDEX"

  else
    log "JAX CPU allowed: installing CPU jax (JAX_VENV)"
    "$(venv_python_jax)" -m pip install -U "jax" || true
  fi

  log "sanity check (TORCH_VENV)"
  set_ld_library_path_for_torch
  sanity_torch

  # ✅ cudnn .so 존재 체크 (python 버전 하드코딩 제거)
  TORCH_SP="$(torch_site_packages || true)"
  if [[ -z "${TORCH_SP}" ]]; then
    warn "cannot resolve torch site-packages to check cudnn"
  else
    CUDNN_SO="${TORCH_SP}/nvidia/cudnn/lib/libcudnn.so.8"
    if [[ ! -e "$CUDNN_SO" ]]; then
      warn "libcudnn.so.8 not found: $CUDNN_SO"
      warn "you may hit: ImportError: libcudnn.so.8"
    else
      log "cudnn OK: $(ls -l "$CUDNN_SO" | awk '{print $9, $5, $6, $7, $8}')"
    fi
  fi

  log "sanity check (JAX_VENV)"
  # ✅ JAX 쪽은 시스템 CUDA 경로를 유지/추가한 상태로 체크
  set_ld_library_path_for_jax
  export ENABLE_JAX_CUDA
  sanity_jax_and_must_gpu_if_requested

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
    tar --no-same-owner --no-same-permissions -xf "$tar_path" -C "$AF_DIR"

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
  export MODELS_DIR OUTPUTS_DIR RFDIFFUSION_DIR
  export TORCH_VENV JAX_VENV
  export AF_DIR COLABDESIGN_DIR

  log "MODELS_DIR=$MODELS_DIR"
  log "AF_DIR=$AF_DIR"
  log "OUTPUTS_DIR=$OUTPUTS_DIR"
  log "SCRIPT_DIR=$SCRIPT_DIR"
  log "RFDIFFUSION_DIR=$RFDIFFUSION_DIR"
  log "TORCH_VENV=$TORCH_VENV"
  log "JAX_VENV=$JAX_VENV"

  export DGLBACKEND="${DGLBACKEND:-pytorch}"
  export DGL_DISABLE_GRAPHBOLT="${DGL_DISABLE_GRAPHBOLT:-1}"
  log "DGLBACKEND=$DGLBACKEND"
  log "DGL_DISABLE_GRAPHBOLT=$DGL_DISABLE_GRAPHBOLT"

  # step 파싱
  local step
  step="$(extract_step_arg "$@")"
  log "detected step=${step:-<empty>}"

  # params 준비는 공통
  ensure_dir "$MODELS_DIR"
  ensure_dir "$OUTPUTS_DIR"
  cmd_download_params
  ensure_unified_params_link

  # ✅ step별 PYTHONPATH 분리 (재발 방지)
  export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH:-}"

  local py
  if [[ "$step" == "alphafold" || "$step" == "proteinMPNN" ]]; then
    py="$(venv_python_jax)"

    # ✅ torch venv nvidia libs는 제거, 시스템 CUDA 경로는 유지/추가
    set_ld_library_path_for_jax
    export ENABLE_JAX_CUDA
    log "Using JAX_VENV python: $py"
    log "PYTHONPATH(jax)=$PYTHONPATH"

    # ✅ 실행 전 반드시 체크 (ENABLE_JAX_CUDA=1이면 GPU 아니면 여기서 바로 죽음)
    sanity_jax_and_must_gpu_if_requested

  else
    py="$(venv_python_torch)"

    # torch step은 nvidia libs path 세팅
    set_ld_library_path_for_torch
    log "Using TORCH_VENV python: $py"
    log "LD_LIBRARY_PATH set (torch/rfdiffusion)"

    # torch step에서만 RFdiffusion path 추가
    export PYTHONPATH="$SCRIPT_DIR/src:$RFDIFFUSION_DIR:${PYTHONPATH:-}"
    log "PYTHONPATH(torch)=$PYTHONPATH"

    sanity_torch
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

  cd "$APP_DIR"
  "$py" "$SCRIPT_DIR/src/main.py" "$@"
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

  "$(venv_python_torch)" -c "import uvicorn, fastapi" >/dev/null 2>&1 || \
    "$(venv_python_torch)" -m pip install -U uvicorn fastapi

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
  env_kv+=("JAX_VENV=$JAX_VENV")
  env_kv+=("PYTHONPATH=$RFDIFFUSION_DIR")
  env_kv+=("MODELS_DIR=$MODELS_DIR")
  env_kv+=("AF_DIR=$AF_DIR")
  env_kv+=("COLABDESIGN_DIR=$COLABDESIGN_DIR")
  env_kv+=("ENABLE_JAX_CUDA=$ENABLE_JAX_CUDA")

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
    "$(venv_python_torch)" -m uvicorn api_server:app --host 0.0.0.0 --port "$PORT" \
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
  JAX_VENV=/opt/venv_jax
  APP_DIR=/workspace/unified
  SCRIPT_DIR=/workspace/unified
  OUTPUTS_DIR=/workspace/unified/outputs
  MODELS_DIR=/models
  PORT=8000
  OPS_DEBUG=0|1

AlphaFold/ColabDesign:
  AF_DIR=/models/alphafold
  COLABDESIGN_DIR=/workspace/colabdesign
  ENABLE_JAX_CUDA=0|1
  JAX_CUDA_WHEEL_INDEX=$JAX_CUDA_WHEEL_INDEX

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