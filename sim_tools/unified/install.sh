#!/usr/bin/env bash
set -euo pipefail

echo "[install.sh] start"

# 기본은 GPU(JAX CUDA) 설치/사용
WITH_JAX_GPU=1

for arg in "$@"; do
  case "$arg" in
    --no-jax-gpu) WITH_JAX_GPU=0 ;;
    -h|--help)
      cat <<'EOF'
Usage:
  bash install.sh [--no-jax-gpu]

Default:
  Installs CUDA-enabled jax/jaxlib (GPU) for AlphaFold (colabdesign).

Options:
  --no-jax-gpu   Skip CUDA-enabled jax/jaxlib install (CPU fallback).
EOF
      exit 0
      ;;
    *)
      echo "[install.sh] Unknown option: $arg"
      exit 1
      ;;
  esac
done

# 0) OS packages
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git aria2 tar unzip ca-certificates curl wget

# 1) python/pip
python3 -V
pip3 install --upgrade pip

# 2) Base python deps (RFdiffusion/유틸)
pip3 install \
  jedi omegaconf hydra-core icecream pyrsistent decorator pyyaml \
  numpy scipy pandas matplotlib tqdm biopython opt_einsum

# (선택) pynvml 경고 없애려면: pynvml 대신 nvidia-ml-py
pip3 install -U nvidia-ml-py
pip3 uninstall -y pynvml || true

# 3) RFdiffusion deps
pip3 install git+https://github.com/NVIDIA/dllogger#egg=dllogger
pip3 install --no-dependencies dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html
pip3 install --no-dependencies e3nn==0.5.5 opt_einsum_fx

# 4) RFdiffusion code (없으면 clone)
mkdir -p /app
if [ ! -d /app/RFdiffusion ]; then
  git clone https://github.com/sokrypton/RFdiffusion.git /app/RFdiffusion
fi

# 5) SE3Transformer install
pip3 install /app/RFdiffusion/env/SE3Transformer

# 6) /app 링크 (네 코드가 /workspace/unified에 있을 때)
mkdir -p /app
ln -snf /workspace/unified/* /app/ || true

# 7) download_params.sh tar 에러 방지 옵션
if [ -f /workspace/unified/download_params.sh ] && grep -q "tar -xf" /workspace/unified/download_params.sh; then
  sed -i 's/tar -xf/tar --no-same-owner --no-same-permissions -xf/g' /workspace/unified/download_params.sh
fi

# 8) colabdesign (ProteinMPNN + AlphaFold wrapper)
pip3 install -U colabdesign

# 9) AlphaFold params symlink 자동 생성
MODELS_DIR="${MODELS_DIR:-/models}"
AF_DIR="${MODELS_DIR}/alphafold"
mkdir -p "${AF_DIR}"

if [ -f "${AF_DIR}/params_model_1_ptm.npz" ]; then
  echo "[install.sh] creating AlphaFold symlinks in ${AF_DIR}"
  cd "${AF_DIR}"

  for i in 1 2 3 4 5; do
    [ -f "params_model_${i}_ptm.npz" ] && ln -sf "params_model_${i}_ptm.npz" "model_${i}_ptm.npz"
  done
  for i in 1 2 3 4 5; do
    [ -f "params_model_${i}.npz" ] && ln -sf "params_model_${i}.npz" "model_${i}.npz"
  done
  for i in 1 2 3 4 5; do
    [ -f "params_model_${i}_multimer_v3.npz" ] && ln -sf "params_model_${i}_multimer_v3.npz" "model_${i}_multimer_v3.npz"
  done
else
  echo "[install.sh] NOTE: ${AF_DIR}/params_model_1_ptm.npz not found yet."
  echo "[install.sh]       (download_params.sh 실행 후 생기면 symlink를 다시 만들면 됨)"
fi

# 10) (기본 ON) JAX CUDA 설치: AlphaFold을 GPU로 돌리기 위함
if [ "${WITH_JAX_GPU}" -eq 1 ]; then
  echo "[install.sh] Installing CUDA-enabled jax/jaxlib (default ON)"
  # CUDA12 계열 타겟 (RunPod에서 흔함)
  pip3 install -U "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

  # 체크
  python3 - <<'PY' || true
import jax
print("jax:", jax.__version__)
print("devices:", jax.devices())
PY
else
  echo "[install.sh] JAX GPU install skipped. (CPU fallback)"
fi

echo "[install.sh] done"