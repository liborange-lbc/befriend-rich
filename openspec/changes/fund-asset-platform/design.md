## 上下文

全新项目，从零构建个人基金资产管理与分析平台。用户持有近百只中美市场基金，需要统一管理、多维度分析和策略自动化提醒。

当前无任何代码基础，需要选择合适的技术栈并设计系统架构。

## 目标 / 非目标

**目标：**
- 构建可本地 Docker 部署、未来可迁移到远端服务器的 Web 应用
- 支持灵活的多维度资产分类模型（用户可自定义层级和类别）
- 自动化行情抓取、技术指标计算、策略检查与通知
- 提供直观的可视化看板（K线、热力图、饼图、趋势图）
- 交互友好（时间选择使用滑块而非输入框）

**非目标：**
- 不做实时交易或下单功能
- 不做多用户/权限系统（个人使用）
- 不做高频数据（分钟级/tick级）
- 不做自动化交易执行
- 不做移动端适配（Web 优先）

## 决策

### 1. 前端：React 18 + TypeScript + Ant Design 5 + ECharts

**选择理由**：
- Ant Design 提供丰富的企业级组件（表格、表单、布局），减少 UI 开发量
- ECharts 在金融可视化方面生态成熟，K线图（candlestick）、热力图（heatmap）、时间轴滑块（dataZoom）均有原生支持
- TypeScript 提供类型安全，降低前后端接口对接错误

**替代方案考量**：
- AntV/G2Plot：Ant 官方图表库，但 K 线图和金融场景支持不如 ECharts
- TradingView Lightweight Charts：专业 K 线组件，但与 Ant Design 集成需要额外工作，且功能集较窄

### 2. 后端：Python 3.11+ + FastAPI

**选择理由**：
- Python 拥有最成熟的金融数据生态（pandas、numpy、tushare、yfinance）
- FastAPI 性能优异、自动生成 OpenAPI 文档、async 原生支持
- SQLAlchemy 2.0 提供类型安全的 ORM

**替代方案考量**：
- Django：全栈框架过重，本项目前后端分离，不需要模板引擎
- Flask：轻量但缺少类型校验和自动文档生成

### 3. 数据库：SQLite

**选择理由**：
- 100只基金 × 365天 × 10年 ≈ 365,000 行日价格数据，SQLite 处理百万行无压力
- 零部署成本，单文件数据库，Docker volume 持久化简单
- 个人使用无并发需求

**替代方案考量**：
- PostgreSQL：功能强大但对个人项目部署负担重，需要独立容器和维护
- 迁移路径：如果未来需要多用户，SQLAlchemy ORM 层可无缝切换到 PostgreSQL

### 4. 回测引擎：自研轻量引擎（基于 pandas）

**选择理由**：
- 需求聚焦于"指标触发 + 定投/条件买卖"，不涉及分钟级回测或多资产组合优化
- backtrader/zipline 学习曲线陡峭，框架约束多，且部分已停止维护
- 基于 pandas DataFrame 实现，代码透明可控，易于扩展新策略

**替代方案考量**：
- backtrader：功能完整但过重，API 设计老旧，且对自定义指标扩展不够灵活
- zipline：Quantopian 停运后社区活跃度下降

### 5. 数据源适配器模式

**选择理由**：
- 定义统一的 `DataSourceAdapter` 接口（fetch_daily_price, fetch_fund_info）
- 当前实现 `TushareAdapter`（A股/国内基金）和 `YahooAdapter`（美股/海外）
- 未来可扩展新数据源只需实现接口，不影响上层逻辑

### 6. 定时调度：APScheduler

**选择理由**：
- 轻量级，嵌入 FastAPI 进程内运行，无需独立调度服务
- 支持 cron 表达式，满足"每小时抓取"和"9/12/14点策略检查"需求
- 持久化任务状态到 SQLite（使用 SQLAlchemyJobStore）

**替代方案考量**：
- Celery + Redis：分布式任务队列，对个人项目过重
- 系统 cron：无法随 Docker 容器优雅管理

### 7. 飞书通知：Webhook API

**选择理由**：
- 用户已有飞书自建应用机器人（有 app_id 和 secret）
- 通过飞书消息 API 发送富文本卡片消息，支持格式化展示策略提醒
- 不依赖第三方通知服务

### 8. 项目结构

```
BeFriend_FundAsset/
├── docker-compose.yml
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx
│       ├── pages/
│       │   ├── Dashboard/          # 大盘看板
│       │   ├── Portfolio/          # 资产管理
│       │   ├── Analysis/           # 基金分析
│       │   ├── Backtest/           # 回测
│       │   └── Settings/           # 设置
│       ├── components/
│       │   ├── Charts/             # ECharts 封装组件
│       │   ├── TimeSlider/         # 时间滑块
│       │   └── Layout/             # 布局组件
│       ├── services/               # API 调用封装
│       ├── types/                  # TypeScript 类型定义
│       └── utils/                  # 工具函数
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                    # 数据库迁移
│   ├── tests/                      # pytest 测试
│   └── app/
│       ├── main.py                 # FastAPI 入口
│       ├── config.py               # 配置管理
│       ├── database.py             # SQLAlchemy 引擎
│       ├── models/                 # ORM 模型
│       │   ├── fund.py
│       │   ├── classification.py
│       │   ├── portfolio.py
│       │   ├── price.py
│       │   ├── strategy.py
│       │   └── exchange_rate.py
│       ├── schemas/                # Pydantic 请求/响应模型
│       ├── api/                    # FastAPI 路由
│       │   ├── funds.py
│       │   ├── classification.py
│       │   ├── portfolio.py
│       │   ├── market_data.py
│       │   ├── analysis.py
│       │   ├── backtest.py
│       │   ├── strategy.py
│       │   └── dashboard.py
│       ├── services/               # 业务逻辑
│       │   ├── market_data/
│       │   │   ├── base.py         # DataSourceAdapter 接口
│       │   │   ├── tushare_adapter.py
│       │   │   ├── yahoo_adapter.py
│       │   │   └── exchange_rate.py
│       │   ├── analysis/
│       │   │   ├── moving_average.py
│       │   │   └── deviation.py
│       │   ├── backtest/
│       │   │   ├── engine.py
│       │   │   ├── strategies.py
│       │   │   └── metrics.py
│       │   ├── portfolio/
│       │   │   ├── recorder.py
│       │   │   └── snapshot.py
│       │   └── notification/
│       │       └── feishu.py
│       └── scheduler/
│           ├── jobs.py             # 任务定义
│           └── setup.py            # APScheduler 配置
└── e2e/                            # Playwright E2E 测试
    ├── playwright.config.ts
    └── tests/
```

### 9. 数据模型核心关系

```
Fund ──1:N──▶ FundDailyPrice       (每日净值+MA+偏差)
Fund ──N:M──▶ ClassCategory        (通过 FundClassMap)
ClassModel ──1:N──▶ ClassCategory  (自引用树形结构)
Fund ──1:N──▶ PortfolioRecord      (每周录入)
PortfolioRecord ──N:1──▶ PortfolioSnapshot (按日期聚合快照)
Fund ──1:N──▶ Strategy             (可选绑定基金)
Strategy ──1:N──▶ BacktestResult   (回测结果)
ExchangeRate                       (独立表，按日期+币种对)
```

### 10. API 设计原则

- RESTful 风格，统一响应格式 `{ success, data, error, meta }`
- 分页参数统一：`page`, `page_size`
- 日期参数统一：ISO 8601 格式（`YYYY-MM-DD`）
- 前端通过 `/api/v1/` 前缀访问所有后端接口

## 风险 / 权衡

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Tushare API 限流/不稳定 | 行情数据获取失败 | 实现重试机制 + 失败告警；Yahoo Finance 作为备用源 |
| 汇率数据源不稳定 | 资产折算不准确 | 多源获取（Yahoo Finance + 备用免费 API）；缓存最近有效汇率 |
| SQLite 并发写入限制 | 定时任务与 Web 请求并发写入冲突 | 使用 WAL 模式；写入操作通过队列串行化 |
| ECharts 大数据量渲染性能 | 10年日数据的 K 线图可能卡顿 | 前端实现数据降采样；使用 dataZoom 限制可视范围 |
| 回测引擎精度 | 简化模型可能与真实交易有偏差 | 明确标注回测假设（不含手续费/滑点等），后续可逐步增加真实度 |
| 飞书 API 变更 | 通知功能中断 | 封装通知接口，便于切换通知渠道 |
