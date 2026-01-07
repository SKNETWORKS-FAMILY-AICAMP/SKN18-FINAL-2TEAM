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


# ★ AlphaFold params 위치 자동 감지
autodetect_af_dir() {
  # 이미 제대로 있으면 그대로 사용
  if [[ -s "${AF_DIR}/params_model_1_ptm.npz" ]]; then
    return 0
  fi
  # 사용자가 AF_DIR 환경변수로 직접 지정한 경우는 건드리지 않음
  if env | grep -q '^AF_DIR='; then
    return 0
  fi
  local found
  found="$(find /workspace /models -type f -name 'params_model_1_ptm.npz' 2>/dev/null | head -n 1 || true)"
  if [[ -n "$found" ]]; then
    AF_DIR="$(dirname "$found")"
    log "autodetect AF_DIR from params: $AF_DIR"
  fi
}

# -----------------------------
# (옵션) JAX GPU indicates attempt
#  - 0: CPU jaxlib 유지 (안전)
#  - 1: CUDA jaxlib 설치 "시도" (실패해도 계속 진행)
# -----------------------------
ENABLE_JAX_CUDA="${ENABLE_JAX_CUDA:-0}"

########################################
# Utils
########################################
log() { echo "[ops] $*"; }
die() { echo "[ops][ERROR] $*" >&2; exit 1; }
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

set_ld_library_path_for_jax() {
  local sp
  sp="$(jax_site_packages || true)"

  if [[ -z "${sp}" ]]; then
    warn "cannot resolve jax site-packages; LD_LIBRARY_PATH not set for jax"
    return 0
  fi

  local nvr="${sp}/nvidia"
  local parts=()

  if [[ -d "$nvr" ]]; then
    while IFS= read -r d; do
      [[ -d "$d" ]] && parts+=("$d")
    done < <(find "$nvr" -maxdepth 3 -type d -name lib 2>/dev/null | sort)
  fi

  if [[ "${#parts[@]}" -eq 0 ]]; then
    warn "no nvidia lib dirs found under: $nvr (LD_LIBRARY_PATH unchanged)"
    return 0
  fi

  export LD_LIBRARY_PATH="$(IFS=:; echo "${parts[*]}"):${LD_LIBRARY_PATH:-}"
  log "LD_LIBRARY_PATH(jax)=${LD_LIBRARY_PATH}"
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

sanity_jax() {
  log "sanity(jax): python=$("$(venv_python_jax)" -V 2>&1 | tr -d '\r')"
  "$(venv_python_jax)" - <<'PY'
try:
  import jax
  dev = jax.devices()
  print("[sanity][jax] version:", jax.__version__)
  print("[sanity][jax] devices:", dev)
  print("[sanity][jax] has_gpu:", any(getattr(d, "platform", "") == "gpu" for d in dev))
except Exception as e:
  print("[sanity][jax] import/devices failed:", repr(e))
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

  # torch 2.2.0+cu121 기준 cuDNN 재고정(안전장치)
  "$(venv_python_torch)" -m pip install -U --no-deps "nvidia-cudnn-cu12==8.9.2.26" || true

  "$(venv_python_torch)" -m pip install \
    -f https://data.dgl.ai/wheels/torch-2.2/cu121/repo.html \
    dgl

  "$(venv_python_torch)" -m pip install -U opt_einsum pyrsistent e3nn

  # API 서버용 패키지
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
  "$(venv_python_jax)" -m pip install -U pip setuptools wheel


  if [[ "$ENABLE_JAX_CUDA" == "1" ]]; then
    log "JAX CUDA mode: jax[cuda12_pip]==0.4.26 (JAX_VENV)"
    # 기존 jax 계열 제거
    "$(venv_python_jax)" -m pip uninstall -y jax jaxlib || true
    # 🔽 CUDA 12용 GPU 빌드 설치
    "$(venv_python_jax)" -m pip install \
      "jax[cuda12_pip]==0.4.26" \
      -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
  else
    log "JAX CPU mode: jax==0.4.26 jaxlib==0.4.26 (JAX_VENV)"
    "$(venv_python_jax)" -m pip uninstall -y jax jaxlib || true
    "$(venv_python_jax)" -m pip install \
      "jax==0.4.26" \
      "jaxlib==0.4.26"
  fi

  # dm-haiku 등 나머지
  "$(venv_python_jax)" -m pip install "dm-haiku==0.0.16"
  # ColabDesign는 의존성 덮어쓰기 막으려면 --no-deps 권장
  if [[ ! -d "$COLABDESIGN_DIR" ]]; then
    log "Cloning ColabDesign into $COLABDESIGN_DIR"
    git clone https://github.com/sokrypton/ColabDesign.git "$COLABDESIGN_DIR"
  fi
  log "installing ColabDesign (editable, no-deps) (JAX_VENV)"
  "$(venv_python_jax)" -m pip install --no-deps -e "$COLABDESIGN_DIR"


  log "sanity check (TORCH_VENV)"
  set_ld_library_path_for_torch
  sanity_torch

  log "sanity check (JAX_VENV)"
  set_ld_library_path_for_jax
  sanity_jax

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

# ✅ 핵심: RFdiffusion ckpt는 /models에 “이미 있으면” 다운로드 스킵하고,
#         /app/RFdiffusion/models 에는 심볼릭 링크로 스테이징
stage_rfdiffusion_ckpts() {
  local rfd_models_dir="${RFD_MODELS_DIR:-$RFDIFFUSION_DIR/models}"
  ensure_dir "$rfd_models_dir"

  local dl_script="$RFDIFFUSION_DIR/scripts/download_models.sh"
  local names=(
    "Base_ckpt.pt"
    "Complex_base_ckpt.pt"
    "Complex_Fold_base_ckpt.pt"
    "InpaintSeq_ckpt.pt"
    "InpaintSeq_Fold_ckpt.pt"
    "ActiveSite_ckpt.pt"
    "Base_epoch8_ckpt.pt"
  )

  # 1) /models에 7개 다 있으면 다운로드 안 함
  local missing=0
  for n in "${names[@]}"; do
    [[ -s "${MODELS_DIR}/${n}" ]] || missing=1
  done

  if [[ "$missing" -eq 1 ]]; then
    # 2) 없으면 download_models.sh로 /models에 받기
    if [[ -x "$dl_script" || -f "$dl_script" ]]; then
      log "RFdiffusion ckpt missing in ${MODELS_DIR}. Downloading via: $dl_script ${MODELS_DIR}"
      bash "$dl_script" "$MODELS_DIR"
    else
      die "RFdiffusion download script not found: $dl_script"
    fi
  else
    log "RFdiffusion ckpt already present in ${MODELS_DIR}. Skipping download."
  fi

  # 3) RFdiffusion이 기본으로 보는 경로(/app/RFdiffusion/models)에 링크 걸어주기
  for n in "${names[@]}"; do
    local src="${MODELS_DIR}/${n}"
    local dst="${rfd_models_dir}/${n}"
    if [[ -s "$src" ]]; then
      ln -sf "$src" "$dst"
    else
      die "RFdiffusion ckpt still missing after download: $src"
    fi
  done

  log "RFdiffusion models staged (symlink) -> ${rfd_models_dir}"
  ls -lh "$rfd_models_dir" || true
}

cmd_download_params() {
  log "download_params start"
  autodetect_af_dir    
  ensure_dir "$MODELS_DIR"

  ########################################
  # AlphaFold params
  ########################################
  ensure_dir "$AF_DIR"
  if [[ ! -s "${AF_DIR}/params_model_1_ptm.npz" ]]; then
    log "AlphaFold params missing; downloading..."
    local tar_path="${AF_DIR}/${AF_PARAMS_TAR_NAME}"
    download_http "$AF_PARAMS_TAR_URL" "$tar_path"

    log "Extracting AlphaFold params (tar --no-same-owner --no-same-permissions)"
    tar --no-same-owner --no-same-permissions -xf "$tar_path" -C "$AF_DIR"

    [[ -s "${AF_DIR}/params_model_1_ptm.npz" ]] || die "AlphaFold params extraction failed"
    log "AlphaFold params ready: ${AF_DIR}"
  else
    log "AlphaFold params OK (exists): ${AF_DIR}/params_model_1_ptm.npz"
  fi

  ########################################
  # RFdiffusion ckpts (7개) - /models 기반
  ########################################
  stage_rfdiffusion_ckpts

  log "download_params done"
}

########################################
# 3) Run
########################################
cmd_run() {
  load_aws_env_from_pid1_if_missing
  refresh_s3_mapping
  autodetect_af_dir 

  log "run start"
  export MODELS_DIR OUTPUTS_DIR RFDIFFUSION_DIR
  export TORCH_VENV JAX_VENV
  export AF_DIR COLABDESIGN_DIR

  export DGLBACKEND="${DGLBACKEND:-pytorch}"
  export DGL_DISABLE_GRAPHBOLT="${DGL_DISABLE_GRAPHBOLT:-1}"

  # step 파싱
  local step
  step="$(extract_step_arg "$@")"
  log "detected step=${step:-<empty>}"

  ensure_dir "$MODELS_DIR"
  ensure_dir "$OUTPUTS_DIR"
  ensure_unified_params_link

  # step별 PYTHONPATH 분리
  export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH:-}"

  local py
  if [[ "$step" == "alphafold" || "$step" == "alphafold3" || "$step" == "protein_mpnn"|| "$step" == "proteinMPNN" ]]; then

    py="$(venv_python_jax)"
    set_ld_library_path_for_jax
    sanity_jax
    log "Using JAX_VENV python: $py"
    log "PYTHONPATH(jax)=$PYTHONPATH"
  else
    py="$(venv_python_torch)"
    set_ld_library_path_for_torch
    # torch step에서만 RFdiffusion 경로 추가
    export PYTHONPATH="$SCRIPT_DIR/src:$RFDIFFUSION_DIR:${PYTHONPATH:-}"
    sanity_torch
    log "Using TORCH_VENV python: $py"
    log "PYTHONPATH(torch)=$PYTHONPATH"
  fi

  if [[ -n "${AWS_REGION:-}" ]]; then
    export AWS_REGION
    export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
  fi
  [[ -n "${AWS_S3_BUCKET:-}" ]] && export AWS_S3_BUCKET
  [[ -n "${AWS_S3_BASE_PATH:-}" ]] && export AWS_S3_BASE_PATH
  [[ -n "${S3_BUCKET:-}" ]] && export S3_BUCKET
  [[ -n "${S3_BASE:-}" ]] && export S3_BASE

  cd "$APP_DIR"
  "$py" "$SCRIPT_DIR/src/main.py" "$@"
}

########################################
# 4) Serve
########################################
cmd_serve() {
  load_aws_env_from_pid1_if_missing
  refresh_s3_mapping
  autodetect_af_dir 

  log "serve start"
  ensure_dir "$APP_DIR"
  ensure_dir "$OUTPUTS_DIR"

  # API 서버는 torch venv 기반
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