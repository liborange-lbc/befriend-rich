# Architecture Overview

## System Summary

BeFriend FundAsset is a personal fund asset management platform for tracking fund portfolios, analyzing market data, running investment strategies, and performing backtests. Single-user, self-hosted via Docker Compose.

## Architecture Layers

```
                    +-----------------------+
                    |      Nginx (:80)      |  SPA static files + API reverse proxy
                    +-----------+-----------+
                                |
              +-----------------+-----------------+
              |                                   |
   +----------v----------+            +-----------v-----------+
   |  Frontend (React)   |            |  Backend (FastAPI)    |
   |  Vite + TypeScript  |            |  Uvicorn :8000        |
   |  Ant Design 6       |            |                       |
   |  ECharts 6          |            |  /api/v1/*            |
   +---------------------+            +-----------+-----------+
                                                  |
                              +-------------------+-------------------+
                              |                   |                   |
                    +---------v------+  +---------v------+  +---------v------+
                    |  SQLAlchemy    |  |  APScheduler   |  |  External APIs |
                    |  SQLite (WAL)  |  |  Background    |  |  Tushare       |
                    |  data/         |  |  Scheduler     |  |  Yahoo Finance |
                    +----------------+  +----------------+  |  AkShare       |
                                                            |  Feishu        |
                                                            |  Anthropic     |
                                                            +----------------+
```

## Backend Modules

| Module | Path | Purpose |
|--------|------|---------|
| API | `app/api/` | 25 routers, all under `/api/v1/` |
| Models | `app/models/` | 20 SQLAlchemy models across 14 files |
| Schemas | `app/schemas/` | Pydantic v2 request/response DTOs |
| Services | `app/services/` | Business logic, organized by domain |
| Scheduler | `app/scheduler/` | APScheduler setup + job definitions |

### Service Sub-modules

| Sub-module | Purpose |
|------------|---------|
| `market_data/` | Adapter pattern for Tushare/Yahoo/AkShare + exchange rates |
| `strategy/` | Strategy evaluation + alert triggering |
| `notification/` | Feishu card message sending (webhook + API) |
| `assistant/` | Anthropic Claude tool-use AI assistant |
| `webank/` | WeBank statement email pull + PDF parse + import |
| `alipay/` | Alipay fund statement email pull + import |
| `portfolio/` | Snapshot generation |
| `analysis/` | Moving average calculation |
| `backtest/` | Backtest engine |
| `market_insight/` | A-share market cap grid |
| `guru/` | Guru holdings from EastMoney + SEC EDGAR |

## Frontend Structure

- **Framework**: React 19 + TypeScript 6 + Vite 8
- **UI Library**: Ant Design 6 + @ant-design/icons 6
- **Charts**: ECharts 6 via echarts-for-react
- **Routing**: react-router-dom 7
- **HTTP Client**: Axios

### Pages (20)

Dashboard, Funds, Portfolio, AssetRecords, Analysis, Backtest, Strategy, Classification, MarketInsight, FundXray, FundCompare, Correlation, Attribution, Valuation, Rebalance, Diary, DataHealth, Scheduler, GuruFocus, MaTiming, Settings (with FundManager + StrategyManager sub-pages)

### Shared Components

- `Layout/AppLayout` - main layout shell
- `Charts/` - PriceChart, TrendChart, HeatmapChart, PieChart
- `Assistant/` - AI copilot panel, button, context
- `HeatmapDrawer`, `ExchangeRateDrawer`, `AssistantDrawer`

## Deployment Topology

```
Docker Compose
  |
  +-- backend (python:3.11-slim, uvicorn :8000)
  |     Volume: sqlite_data -> /app/data
  |     Env: .env file
  |
  +-- frontend (node:20-alpine build -> nginx:alpine :80)
        nginx reverse proxy /api/ -> backend:8000
```

## Key Design Decisions

1. **SQLite with WAL mode** - single-user, no need for PostgreSQL. FK constraints enabled via PRAGMA.
2. **No Alembic migrations** - tables auto-created via `Base.metadata.create_all()` at startup.
3. **APScheduler in-process** - runs inside the same uvicorn process, started/stopped via FastAPI lifespan.
4. **Adapter pattern for data sources** - abstract `DataSourceAdapter` base class with Tushare/Yahoo/AkShare implementations.
5. **System config in DB** - `system_config` table stores all runtime configuration, with env var migration on first run.
