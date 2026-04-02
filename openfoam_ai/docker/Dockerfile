# OpenFOAM AI Agent Docker镜像
# 基于OpenFOAM Foundation版本

FROM opencfd/openfoam-default:11

USER root

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    python3-dev \
    build-essential \
    git \
    wget \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 设置Python3.10为默认
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# 升级pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 创建工作目录
WORKDIR /workspace

# 复制依赖文件并安装
COPY requirements.txt /workspace/
RUN pip install --no-cache-dir -r /workspace/requirements.txt

# 复制项目代码
COPY . /workspace/openfoam_ai

# 设置环境变量
ENV PYTHONPATH=/workspace/openfoam_ai:$PYTHONPATH
ENV PATH=/usr/local/bin:$PATH
ENV FOAM_USER_LIBBIN=/workspace/openfoam_ai/lib
ENV FOAM_USER_APPBIN=/workspace/openfoam_ai/bin

# 切换到OpenFOAM用户
USER openfoam

# 工作目录
WORKDIR /workspace/openfoam_ai

# 默认命令
CMD ["/bin/bash"]
