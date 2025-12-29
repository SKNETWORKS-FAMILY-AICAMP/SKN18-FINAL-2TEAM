#!/usr/bin/env bash
set -euo pipefail

echo "[install.sh] start"

# 이미 설치됐으면 스킵 (재실행 빨라짐)
MARKER="/workspace/.unified_installed"
if [ -f "$MARKER" ]; then
  echo "[install.sh] already installed. skip."
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive

# 0) OS 패키지
apt-get update
apt-get install -y git aria2 tar unzip ca-certificates curl wget

# 1) python/pip
python3 -V
pip3 install --upgrade pip

# 1.5) torch 버전 고정 (RunPod 기본 torch가 달라도 동일하게 맞춤)
pip3 install --index-url https://download.pytorch.org/whl/cu124 torch==2.4.0

# 2) 파이썬 deps (RFdiffusion/유틸)
pip3 install \
  jedi omegaconf hydra-core icecream pyrsistent decorator pyyaml \
  numpy scipy pandas matplotlib tqdm biopython opt_einsum \
  pydantic>=2

# (선택) pynvml 경고 없애려면: pynvml 대신 nvidia-ml-py
pip3 install -U nvidia-ml-py
pip3 uninstall -y pynvml || true

# 3) RFdiffusion deps
pip3 install git+https://github.com/NVIDIA/dllogger#egg=dllogger
pip3 install --no-dependencies dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html
pip3 install --no-dependencies e3nn==0.5.5 opt_einsum_fx

# 4) RFdiffusion 코드 (없으면 clone)
mkdir -p /app
if [ ! -d /app/RFdiffusion ]; then
  git clone https://github.com/sokrypton/RFdiffusion.git /app/RFdiffusion
fi

# 5) SE3Transformer 설치
pip3 install /app/RFdiffusion/env/SE3Transformer

# 6) /app 링크 (네 코드가 /workspace/unified에 있을 때)
ln -snf /workspace/unified/* /app/ || true

# 7) download_params.sh tar 에러 방지 옵션
if grep -q "tar -xf" /workspace/unified/download_params.sh; then
  sed -i 's/tar -xf/tar --no-same-owner --no-same-permissions -xf/g' /workspace/unified/download_params.sh
fi

# 설치 완료 마커
touch "$MARKER"
echo "[install.sh] done"