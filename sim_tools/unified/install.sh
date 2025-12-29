#!/usr/bin/env bash
set -euo pipefail

echo "[install.sh] start"

# 0) OS 패키지 (없으면 설치)
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git aria2 tar unzip ca-certificates curl wget

# 1) python/pip
python3 -V
pip3 install --upgrade pip

# 2) 파이썬 deps (RFdiffusion/유틸)
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

# 4) RFdiffusion 코드 (없으면 clone)
mkdir -p /app
if [ ! -d /app/RFdiffusion ]; then
  git clone https://github.com/sokrypton/RFdiffusion.git /app/RFdiffusion
fi

# 5) SE3Transformer 설치
pip3 install /app/RFdiffusion/env/SE3Transformer

# 6) /app 링크 (네 코드가 /workspace/unified에 있을 때)
mkdir -p /app
ln -snf /workspace/unified/* /app/ || true

# 7) download_params.sh tar 에러 방지 옵션(아직 반영 안됐으면)
if grep -q "tar -xf" /workspace/unified/download_params.sh; then
  sed -i 's/tar -xf/tar --no-same-owner --no-same-permissions -xf/g' /workspace/unified/download_params.sh
fi

echo "[install.sh] done"