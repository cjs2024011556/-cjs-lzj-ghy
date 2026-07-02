# A1 — 基于多模态大模型技术的设备检修知识检索与作业系统

> **赛题**：聚焦工业（钢铁/汽车制造等）产线设备检修场景，提供多模态智能检索、标准化作业指引、知识沉淀与更新的一体化系统。
>
> **部署目标**：龙芯 LoongArch + 银河麒麟 V11/V10（0 分硬约束）
>
> **模型来源**：阿里云百炼平台（DashScope）— 云端 API + 本地开源同源模型双模式

---

## ✨ 核心特性

- 🔍 **多模态知识检索**：支持文本 / 故障图片 / 设备型号输入，跨模态语义匹配
- 📋 **标准化作业指引**：基于设备类型与检修等级的步骤化 SOP，合规校验
- 🧠 **多模态大模型双模式**：阿里云百炼 API（默认）+ 本地 Qwen2-VL-7B（降级），可热切换
- 🔄 **知识沉淀闭环**：一线人员上传 → 审核 → 入库 → 检索，全流程可追溯
- 🎨 **工业风 UI**：深色高对比、响应式、强光下可读
- 🛡️ **国产化全栈**：LoongArch + 麒麟 + 百炼模型生态

---

## 🏗️ 架构

```
前端 (Vue 3 + Element Plus)
    ↓ HTTPS/REST
后端 (Python 3.11 + FastAPI)
    ↓
模型适配层（双模式）
    ├── Cloud: 阿里云百炼 API (qwen-vl-max)
    └── Local: Qwen2-VL-7B-Instruct (transformers)
    ↓
数据层 (PostgreSQL + Milvus + Neo4j + MinIO)
    ↓
部署 (LoongArch + 银河麒麟 V11/V10)
```

详见 [docs/02-功能设计.md](docs/02-功能设计.md)

---

## 📦 项目结构

```
A1/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/          # 路由层
│   │   ├── services/     # 业务服务
│   │   ├── llm/          # 模型适配层（双模式）
│   │   ├── core/         # 配置、日志、异常
│   │   ├── db/           # 数据库连接
│   │   ├── models/       # ORM 模型
│   │   └── schemas/      # Pydantic
│   ├── data/             # 知识库数据
│   ├── tests/
│   └── pyproject.toml
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── views/        # 页面
│   │   ├── components/   # 组件
│   │   ├── api/          # API 客户端
│   │   ├── stores/       # Pinia
│   │   └── router/
│   └── package.json
├── deploy/               # 部署脚本（LoongArch + 麒麟）
│   ├── install.sh
│   ├── nginx.conf
│   └── a1-backend.service
├── docs/                 # 项目文档
│   ├── 01-需求分析.md
│   ├── 02-功能设计.md
│   ├── 03-产品说明书.md
│   ├── 04-测试报告.md
│   ├── 05-部署文档.md
│   ├── demo.pptx
│   └── demo-video.mp4
├── docker-compose.yml    # 一键启动（开发）
└── README.md
```

---

## 🚀 快速开始

### 开发环境

```bash
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev

# 访问
# 前端: http://localhost:5173
# 后端: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### Docker 一键启动

```bash
docker compose up -d
```

### LoongArch + 麒麟部署

详见 [docs/05-部署文档.md](docs/05-部署文档.md) 和 [deploy/install.sh](deploy/install.sh)

---

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| 后端 | Python 3.11 + FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 + Alembic |
| 数据库 | PostgreSQL 15 |
| 向量库 | Milvus 2.x |
| 知识图谱 | Neo4j 5.x |
| 对象存储 | MinIO |
| Embedding | BGE-M3 |
| LLM 云端 | 阿里云百炼 (qwen-vl-max) |
| LLM 本地 | Qwen2-VL-7B-Instruct |
| 文档解析 | MinerU / PaddleOCR |
| 反向代理 | Nginx |
| 进程管理 | systemd |
| 容器 | Docker + docker-compose |

---

## 📋 文档索引

- [01-需求分析.md](docs/01-需求分析.md) — 业务背景、用户角色、功能/非功能需求
- [02-功能设计.md](docs/02-功能设计.md) — 架构、模块、接口、关键流程
- [03-产品说明书.md](docs/03-产品说明书.md) — 用户使用手册
- [04-测试报告.md](docs/04-测试报告.md) — 测试用例与结果
- [05-部署文档.md](docs/05-部署文档.md) — LoongArch + 麒麟 + 百炼部署指南

---

## 📊 评分对标

| 评分项 | 占比 | 实现 |
|---|---|---|
| 功能完整性 | 30% | 4 项核心功能（检索/作业/知识/界面）全实现 |
| 用户体验 | 20% | 工业风 UI、便捷交互、稳定性 |
| 创新与实用性 | 20% | 国产化全栈 + 跨模态检索 + 知识图谱 + 反馈闭环 |
| 文档与演示 | 20% | 5 份文档 + PPT + 7 分钟视频 |
| 商业可行性 | 10% | ROI、TCO、推广路径 |

---

## 📝 License

Apache 2.0
