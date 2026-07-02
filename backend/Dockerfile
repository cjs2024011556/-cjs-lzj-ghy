# A1 设备检修智能系统 - 后端 Dockerfile
# 多阶段构建，兼容 LoongArch + x86

# ---- 阶段 1: 构建基础镜像 ----
FROM python:3.11-slim AS base

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    gcc \
    libffi-dev \
    libssl-dev \
    fonts-noto-cjk \
    locales \
    && locale-gen zh_CN.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY requirements.txt pyproject.toml ./

# 安装 Python 依赖
# LoongArch 注意事项：部分包可能需要找适配的 wheel
# 如果遇到 wheel 不可用，注释掉对应行重试
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ---- 阶段 2: 运行时镜像 ----
FROM base AS runtime

# 复制应用代码
COPY app ./app
COPY scripts ./scripts

# 创建非 root 用户
RUN useradd -m -u 1000 a1user && \
    mkdir -p /app/uploads /app/logs /app/data && \
    chown -R a1user:a1user /app

USER a1user

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
