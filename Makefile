# A1 设备检修智能系统 - 便捷命令
# Windows 用户可使用对应的 .ps1 脚本或手动执行

.PHONY: help install dev backend frontend test build docker clean

help:
	@echo "A1 设备检修智能系统 - 可用命令"
	@echo ""
	@echo "  install    安装所有依赖（后端 + 前端）"
	@echo "  dev        启动开发服务（后端 + 前端）"
	@echo "  backend    仅启动后端"
	@echo "  frontend   仅启动前端"
	@echo "  test       运行后端测试"
	@echo "  import     导入内置示例数据"
	@echo "  build      构建生产产物"
	@echo "  docker     Docker Compose 启动"
	@echo "  clean      清理构建产物"

# ---- 安装 ----
install:
	@echo "📦 安装后端依赖..."
	cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
	@echo "📦 安装前端依赖..."
	cd frontend && npm install

# ---- 开发 ----
dev:
	@echo "🚀 启动后端 (端口 8000)..."
	cd backend && .venv/Scripts/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo "🚀 启动前端 (端口 5173)..."
	cd frontend && npm run dev

backend:
	cd backend && .venv/Scripts/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# ---- 测试 ----
test:
	cd backend && .venv/Scripts/activate && pytest -v

# ---- 数据导入 ----
import:
	cd backend && .venv/Scripts/activate && python -m scripts.import_sample_data

# ---- 构建 ----
build:
	@echo "🔨 构建前端..."
	cd frontend && npm run build
	@echo "✅ 构建完成"

# ---- Docker ----
docker:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ---- 清理 ----
clean:
	@echo "🧹 清理..."
	rm -rf backend/.venv
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf backend/data/postgres
	rm -rf backend/data/milvus
	rm -rf backend/data/neo4j
	rm -rf backend/data/minio
	@echo "✅ 清理完成"
