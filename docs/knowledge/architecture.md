# BeFriend 基金资产管理平台 — 系统架构

## 技术栈
- **前端**: React 19 + TypeScript + Ant Design 6 + Vite + ECharts
- **后端**: Python FastAPI + SQLAlchemy + SQLite (WAL 模式)
- **AI 助手**: CCRemote Agent（Claude API）
- **数据源**: AkShare（A股/基金）、Yahoo Finance（美股）

## 项目结构
```
BeFriend_FundAsset/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI 路由（RESTful 端点）
│   │   ├── models/         # SQLAlchemy 数据模型
│   │   ├── schemas/        # Pydantic 请求/响应 Schema
│   │   ├── services/       # 业务逻辑服务层
│   │   │   ├── webank/     # 微众银行导入相关
│   │   │   ├── market_data/# 市场数据获取
│   │   │   └── ...
│   │   ├── scheduler/      # APScheduler 定时任务
│   │   ├── database.py     # 数据库连接配置
│   │   └── main.py         # FastAPI 应用入口
│   ├── data/               # SQLite 数据库文件
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/     # 通用组件
│   │   │   ├── Assistant/  # AI 助手面板
│   │   │   └── Layout/     # 应用布局
│   │   ├── pages/          # 页面组件
│   │   │   ├── Dashboard/  # 大盘看板
│   │   │   ├── Portfolio/  # 资金大盘
│   │   │   ├── Analysis/   # 基金分析
│   │   │   ├── Backtest/   # 策略回测
│   │   │   └── Classification/ # 分类管理
│   │   ├── services/       # API 调用层
│   │   └── types/          # TypeScript 类型定义
│   └── .env                # 环境配置（端口等）
└── docs/
    └── knowledge/          # AI 助手知识库文档
```

## 核心数据流
1. **数据录入**: 微众银行对账单(Excel/PDF) → 解析 → 基金匹配(AkShare) → AI 分类 → 写入持仓
2. **数据展示**: 前端页面 → API 请求 → FastAPI → SQLAlchemy 查询 → JSON 响应
3. **定时任务**: APScheduler → 每日汇率更新、价格回填、自动邮件拉取

## 页面功能
| 页面 | 路径 | 功能 |
|------|------|------|
| 大盘看板 | /dashboard | 基金行情、K线、均值偏差热力图、策略提醒、汇率 |
| 资金大盘 | /portfolio | 总资产、模型配比饼图、资产趋势、持仓 TOP5 |
| 基金分析 | /analysis | 单只基金详情、价格走势、均线分析 |
| 策略回测 | /backtest | 回测配置、净值曲线、交易明细、指标对比 |
| 分类管理 | /classification | 分类模型 CRUD、基金分类映射 |
