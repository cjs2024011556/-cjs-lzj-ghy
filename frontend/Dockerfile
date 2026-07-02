# A1 设备检修智能系统 - 前端 Dockerfile
# 多阶段构建：Node 构建 → Nginx 服务

# ---- 阶段 1: 构建 ----
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package.json ./
RUN npm install --no-audit --no-fund

# 复制源码
COPY . .

# 构建
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# ---- 阶段 2: Nginx 服务 ----
FROM nginx:1.25-alpine

# 复制自定义 nginx 配置
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
