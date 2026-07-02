# A1 Frontend — 设备检修智能系统前端

Vue 3 + TypeScript + Element Plus 工业风前端。

## 技术栈

- **框架**: Vue 3 + TypeScript
- **构建**: Vite 5
- **UI**: Element Plus（暗色工业风）
- **状态**: Pinia
- **路由**: Vue Router 4
- **HTTP**: Axios
- **图表**: ECharts
- **Markdown**: marked

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问
# http://localhost:5173
```

## 目录结构

```
src/
├── api/          # API 客户端
│   ├── index.ts
│   ├── retrieval.ts
│   ├── guide.ts
│   ├── knowledge.ts
│   ├── llm.ts
│   └── health.ts
├── stores/       # Pinia stores
│   └── llm.ts
├── views/        # 页面
│   ├── Layout.vue       # 主布局
│   ├── Home.vue         # 首页 Dashboard
│   ├── Retrieval.vue    # 多模态检索 (F2)
│   ├── OperationGuide.vue  # 作业指引 (F3)
│   ├── Knowledge.vue    # 知识管理 (F4)
│   └── Admin.vue        # 后台管理
├── styles/       # 全局样式
│   └── main.scss
├── router/       # 路由
│   └── index.ts
├── App.vue
└── main.ts
```

## 4 项核心功能

| 功能 | 页面 | API |
|---|---|---|
| F1. 可视化界面 | Layout | - |
| F2. 多模态知识检索 | Retrieval.vue | /api/v1/retrieval/* |
| F3. 标准化作业指引 | OperationGuide.vue | /api/v1/operation-guide/* |
| F4. 知识沉淀与更新 | Knowledge.vue, Admin.vue | /api/v1/knowledge/* |

## 主题色（工业风）

- 主色：`#00d4ff`（工业蓝）
- 背景：`#0a1929`（深色）
- 强调：`#00d97e`（成功）、`#ff4757`（危险）

## 部署

详见 [../docs/05-部署文档.md](../docs/05-部署文档.md)
