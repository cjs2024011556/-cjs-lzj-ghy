# MotoEngine

智能文档处理与向量检索引擎

## 项目结构

```
MotoEngine/
├── .venv/                  # Python虚拟环境
├── motoengine/             # 核心Python包
│   ├── .env                # 环境变量配置
│   ├── __init__.py         # 包初始化
│   ├── __main__.py         # CLI入口
│   ├── config.py           # 全局配置
│   ├── func/               # 核心功能模块
│   ├── route/              # FastAPI路由
│   ├── static/             # 静态资源
│   └── templates/          # HTML模板
├── data/                   # 数据存储
├── uploads/                # 用户上传文件
├── README.md               # 项目说明
└── pyproject.toml          # 依赖管理
```

## 快速开始

1. 激活虚拟环境
2. 安装依赖：`pip install -e .`
3. 配置API密钥：编辑 `motoengine/.env`
4. 运行应用：`python -m motoengine`

## License

MIT
