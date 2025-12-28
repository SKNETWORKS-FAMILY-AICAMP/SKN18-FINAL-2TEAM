FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# OS deps
RUN apt-get update && apt-get install -y \
    python3 python3-pip python-is-python3 \
    git wget curl ca-certificates \
    unzip tar bash aria2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip

# PyTorch (CUDA 12.4)
RUN pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124

# ColabDesign / RFdiffusion deps
RUN pip install \
    jedi omegaconf hydra-core icecream pyrsistent pynvml decorator pyyaml \
 && pip install git+https://github.com/NVIDIA/dllogger#egg=dllogger \
 && pip install --no-dependencies dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html \
 && pip install --no-dependencies e3nn==0.5.5 opt_einsum_fx

# RFdiffusion
RUN git clone https://github.com/sokrypton/RFdiffusion.git /app/RFdiffusion \
 && cd /app/RFdiffusion/env/SE3Transformer \
 && pip install .

# ColabDesign (v1.1.1)
RUN pip install -q git+https://github.com/sokrypton/ColabDesign.git@v1.1.1 \
 && python -c "import colabdesign; print('colabdesign ok')"

# ananas binary (symmetry auto-detect) - 지금은 symmetry 안 쓰더라도 코랩과 맞추는게 좋음
RUN wget -qnc https://files.ipd.uw.edu/krypton/ananas -O /app/ananas \
 && chmod +x /app/ananas

# unified files
COPY sim_tools/unified/run.sh /app/run.sh
COPY sim_tools/unified/download_params.sh /app/download_params.sh
COPY sim_tools/unified/config.yml /app/config.yml
COPY sim_tools/unified/src /app/src

RUN chmod +x /app/run.sh /app/download_params.sh

# runtime dirs
RUN mkdir -p /outputs /models
ENV MODELS_DIR=/models
ENV OUTPUTS_DIR=/outputs

RUN mkdir -p /app/RFdiffusion/models

ENTRYPOINT ["/app/run.sh"]