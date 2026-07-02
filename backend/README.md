# A1 Backend — 设备检修智能系统后端

基于 FastAPI + 多模态大模型的设备检修知识检索与作业系统后端。

## 技术栈

- **Web 框架**: FastAPI 0.110+
- **Python**: 3.11+
- **数据库**: PostgreSQL 15 + Milvus 2.4 + Neo4j 5.x + MinIO
- **LLM**: 阿里云百炼平台（云端 API）+ Qwen2-VL-7B（本地降级）
- **Embedding**: BGE-M3
- **部署**: Docker + systemd + Nginx

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 填入 DASHSCOPE_API_KEY

# 4. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 目录结构

```
backend/
├── app/
│   ├── api/v1/        # 路由层
│   ├── core/          # 配置、日志
│   ├── db/            # 数据库连接
│   ├── llm/           # 模型适配层（双模式）
│   ├── models/        # ORM 模型
│   ├── schemas/       # Pydantic
│   ├── services/      # 业务服务
│   └── utils/
├── data/              # 知识库数据
│   ├── raw/           # 原始文档
│   ├── indexed/       # 索引后数据
│   └── models/        # 本地模型
├── tests/             # 测试
└── pyproject.toml
```

## API 文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI: http://localhost:8000/openapi.json

## 双模式切换

通过 `LLM_MODE` 环境变量切换：

```bash
# 云端 API 模式（默认）
LLM_MODE=cloud

# 本地模型模式
LLM_MODE=local
```

也可以通过 API 动态切换：

```bash
curl -X POST http://localhost:8000/api/v1/llm/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "local"}'
```

## 测试

```bash
pytest -v
```

## 部署

详见 [../docs/05-部署文档.md](../docs/05-部署文档.md) 和 [../deploy/install.sh](../deploy/install.sh)
