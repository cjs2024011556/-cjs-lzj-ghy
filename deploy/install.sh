#!/bin/bash
# ============================================
# A1 设备检修智能系统 - LoongArch + 麒麟部署脚本
# ============================================

set -e

echo "==================================="
echo "  A1 系统部署脚本"
echo "  目标: LoongArch + 银河麒麟 V11/V10"
echo "==================================="

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查架构
ARCH=$(uname -m)
echo -e "${YELLOW}当前架构: ${ARCH}${NC}"
if [ "$ARCH" != "loongarch64" ]; then
    echo -e "${YELLOW}⚠️  警告: 当前不是 loongarch64，部署可能需要调整${NC}"
fi

# 检查 OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo -e "${YELLOW}操作系统: ${NAME} ${VERSION}${NC}"
fi

# ---- 1. 系统依赖 ----
echo -e "\n${GREEN}[1/6] 安装系统依赖${NC}"
sudo yum install -y python3.11 python3.11-devel python3-pip \
    nodejs npm git curl wget nginx \
    postgresql postgresql-contrib \
    java-17-openjdk  # Neo4j 需要

# ---- 2. Python 虚拟环境 ----
echo -e "\n${GREEN}[2/6] 创建 Python 虚拟环境${NC}"
cd /opt/a1/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ---- 3. 数据库初始化 ----
echo -e "\n${GREEN}[3/6] 初始化数据库${NC}"
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo -u postgres psql -c "CREATE USER a1_user WITH PASSWORD 'a1_password';"
sudo -u postgres psql -c "CREATE DATABASE a1_maintenance OWNER a1_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE a1_maintenance TO a1_user;"

# ---- 4. Milvus / Neo4j / MinIO 启动 ----
echo -e "\n${GREEN}[4/6] 启动 Milvus / Neo4j / MinIO${NC}"
cd /opt/a1
sudo docker compose up -d postgres milvus-standalone neo4j minio

# 等待服务就绪
echo "等待数据库服务启动..."
sleep 30

# ---- 5. 前端构建 ----
echo -e "\n${GREEN}[5/6] 构建前端${NC}"
cd /opt/a1/frontend
npm install
npm run build

# ---- 6. 后端服务注册 ----
echo -e "\n${GREEN}[6/6] 注册后端服务${NC}"
sudo cp /opt/a1/deploy/a1-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable a1-backend
sudo systemctl start a1-backend

# Nginx 配置
sudo cp /opt/a1/deploy/nginx.conf /etc/nginx/conf.d/a1.conf
sudo nginx -t
sudo systemctl restart nginx

# ---- 7. 健康检查 ----
echo -e "\n${GREEN}[7/7] 健康检查${NC}"
sleep 10
curl -f http://localhost:8000/api/v1/health && echo -e "${GREEN}✅ 部署成功${NC}" || echo -e "${RED}❌ 服务未就绪，请检查日志${NC}"

echo -e "\n${GREEN}===================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}  访问地址: http://<服务器IP>${NC}"
echo -e "${GREEN}  API 文档: http://<服务器IP>/docs${NC}"
echo -e "${GREEN}===================================${NC}"
