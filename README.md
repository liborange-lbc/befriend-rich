# BeFriend FundAsset

基金资产管理与分析平台，支持多币种投资组合跟踪、技术分析、策略回测与自动化告警。

## 功能特性

### 市场数据
- 多数据源集成（Tushare、Yahoo Finance、AkShare）
- 自动拉取基金净值与均线偏离度（MA30/60/90/120/180/360）
- 汇率追踪（USD/CNY、HKD/CNY），支持 10 年历史数据回溯
- 定时任务自动更新行情数据

### 投资组合
- 多币种持仓记录（CNY、USD、HKD）
- 周度快照与趋势分析
- Top5 持仓排名与分类占比饼图
- 按自定义分类模型聚合展示

### 基金分类
- 多层级分类体系（支持树形结构）
- 多分类模型并行（如按资产类别、按地域、按策略等）
- 基金-分类灵活映射

### 策略与回测
- 策略配置（买入/卖出条件）
- 回测引擎：收益率、夏普比率、最大回撤、胜率、盈亏比
- 权益曲线与交易日志
- 策略自动评估与偏离度告警

### 通知
- 飞书 Webhook 告警推送
- 可配置推送频率与策略检查时段

### 系统配置
- 数据库动态配置管理（database > 环境变量 > 默认值）
- 前端设置页面可视化编辑
- 密钥字段脱敏显示

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 19 + TypeScript + Vite + Ant Design 6 + ECharts |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + Alembic |
| 数据库 | SQLite（WAL 模式） |
| 定时任务 | APScheduler |
| 容器化 | Docker Compose + Nginx 反向代理 |
| 测试 | Pytest + Playwright |

## 项目结构

```
BeFriend_FundAsset/
├── backend/
│   ├── app/
│   │   ├── api/              # 路由层（funds, portfolio, strategy, backtest, dashboard, analysis, classification, config, market_data）
│   │   ├── models/           # ORM 模型（fund, portfolio, price, strategy, classification, config）
│   │   ├── schemas/          # Pydantic 数据传输对象
│   │   ├── services/         # 业务逻辑
│   │   │   ├── market_data/  # 数据适配器（Tushare, Yahoo, AkShare）
│   │   │   ├── backtest/     # 回测引擎
│   │   │   ├── strategy/     # 策略评估
│   │   │   ├── portfolio/    # 组合快照
│   │   │   ├── notification/ # 飞书通知
│   │   │   └── analysis/     # 技术分析
│   │   ├── scheduler/        # 定时任务
│   │   ├── main.py           # 应用入口
│   │   ├── config.py         # 配置
│   │   ├── database.py       # 数据库引擎
│   │   └── response.py       # 统一响应格式
│   ├── tests/                # 测试
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example          # 环境变量模板
├── frontend/
│   ├── src/
│   │   ├── pages/            # 页面组件（Dashboard, Portfolio, Analysis, Classification, Backtest, Strategy, Settings）
│   │   ├── components/       # 公共组件（AppLayout, PieChart, TrendChart, PriceChart, HeatmapChart 等）
│   │   ├── services/         # API 客户端
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── App.tsx           # 根组件与路由
│   │   └── main.tsx          # 入口
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── nginx.conf            # Nginx 配置（API 代理 + SPA 路由）
├── docker-compose.yml
└── README.md
```

## 快速开始

### 环境要求

- Docker & Docker Compose（容器化部署）
- Python 3.11+（本地后端开发）
- Node.js 20+（本地前端开发）

### Docker 部署（推荐）

```bash
# 克隆仓库
git clone https://github.com/liborange-lbc/befriend-rich.git
cd befriend-rich

# 创建环境变量文件
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入必要的 API Token

# 启动服务
docker-compose up -d

# 访问
# 前端：http://localhost:3000
# 后端 API：http://localhost:8000
# Swagger 文档：http://localhost:8000/docs
```

### 本地开发

**后端：**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入配置
uvicorn app.main:app --reload --port 8000
```

**前端：**

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

## 环境变量

在 `backend/.env` 中配置：

| 变量 | 说明 | 必填 |
|------|------|------|
| `DATABASE_URL` | 数据库连接字符串 | 是（默认 SQLite） |
| `TUSHARE_TOKEN` | Tushare API Token | 使用 Tushare 数据源时必填 |
| `FEISHU_APP_ID` | 飞书应用 ID | 使用飞书通知时必填 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 使用飞书通知时必填 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook 地址 | 使用飞书通知时必填 |

以下配置可通过前端「设置」页面或数据库直接管理：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `scheduler_market_cron` | `0 * * * *` | 行情拉取 Cron 表达式 |
| `scheduler_strategy_hours` | `9,12,14` | 策略检查时段 |
| `exchange_rate_pairs` | `USD/CNY,HKD/CNY` | 汇率跟踪货币对 |
| `backfill_years` | `10` | 历史数据回溯年数 |
| `default_rate_usd_cny` | `7.25` | USD/CNY 兜底汇率 |
| `default_rate_hkd_cny` | `0.93` | HKD/CNY 兜底汇率 |

## API 概览

| 模块 | 路径 | 功能 |
|------|------|------|
| 基金管理 | `/api/v1/funds` | CRUD、回填状态查询 |
| 投资组合 | `/api/v1/portfolio` | 持仓记录、快照、Top5 |
| 分类 | `/api/v1/classification` | 分类模型、类别、映射、树形结构 |
| 行情数据 | `/api/v1/market-data` | 数据拉取、历史回填、汇率历史 |
| 技术分析 | `/api/v1/analysis` | 日线数据、偏离度汇总 |
| 仪表盘 | `/api/v1/dashboard` | 总览、基金行情、最近告警 |
| 策略 | `/api/v1/strategy` | 策略 CRUD、告警日志 |
| 回测 | `/api/v1/backtest` | 执行回测、查看结果 |
| 配置 | `/api/v1/config` | 系统配置读写 |

完整 API 文档请访问 http://localhost:8000/docs（Swagger UI）。

## 测试

```bash
cd backend
pytest                   # 运行全部测试
pytest -v                # 详细输出
pytest --cov=app         # 覆盖率报告
```

## 界面模式

应用包含两个主导航模式：

- **有知**（市场洞察）：仪表盘总览、技术分析、偏离度热力图
- **有行**（资产管理）：持仓记录、分类管理、策略回测

## License

MIT
