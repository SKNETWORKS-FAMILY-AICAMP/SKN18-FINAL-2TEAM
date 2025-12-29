FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip python-is-python3 \
    git wget curl ca-certificates \
    unzip tar bash aria2 \
    openssh-server \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /var/run/sshd

# SSH 설정: root는 키 기반 로그인만 허용(패스워드 로그인 금지)
RUN sed -i 's/#PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config \
 && sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

RUN pip3 install --upgrade pip

# PyTorch (CUDA 12.4)
RUN pip3 install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124

# ColabDesign / RFdiffusion deps
RUN pip3 install \
    jedi omegaconf hydra-core icecream pyrsistent pynvml decorator pyyaml \
 && pip3 install git+https://github.com/NVIDIA/dllogger#egg=dllogger \
 && pip3 install --no-dependencies dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html \
 && pip3 install --no-dependencies e3nn==0.5.5 opt_einsum_fx

# RFdiffusion
RUN git clone https://github.com/sokrypton/RFdiffusion.git /app/RFdiffusion \
 && cd /app/RFdiffusion/env/SE3Transformer \
 && pip3 install .

# ColabDesign (v1.1.1)
RUN pip3 install -q git+https://github.com/sokrypton/ColabDesign.git@v1.1.1 \
 && python3 -c "import colabdesign; print('colabdesign ok')"

# ananas binary
RUN wget -qnc https://files.ipd.uw.edu/krypton/ananas -O /app/ananas \
 && chmod +x /app/ananas

# unified files
COPY sim_tools/unified/run.sh /app/run.sh
COPY sim_tools/unified/download_params.sh /app/download_params.sh
COPY sim_tools/unified/config.yml /app/config.yml
COPY sim_tools/unified/src /app/src

RUN chmod +x /app/run.sh /app/download_params.sh

RUN mkdir -p /outputs /models /app/RFdiffusion/models
ENV MODELS_DIR=/models
ENV OUTPUTS_DIR=/outputs

# ✅ entrypoint 추가
COPY sim_tools/unified/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]