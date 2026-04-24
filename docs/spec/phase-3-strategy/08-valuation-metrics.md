# #8 估值指标

## 概述
指数PE/PB历史分位数、估值温度计、基于估值的定投系数建议。

## 设计

### 数据模型
- **新表** `index_valuation` — 存储指数估值历史
  - index_code, date, pe, pb, pe_percentile, pb_percentile

### 后端
- **服务** `backend/app/services/valuation_service.py`
  - 从已有 market_insight index_kline 数据获取 PE（已有 pe_ratio 字段）
  - 计算历史分位数（PE 在过去 N 年中的百分位）
  - 估值温度: pe_percentile 映射到 0-100（0=极度低估, 100=极度高估）
  - 定投系数: 基于温度的投资金额建议倍数

- **API** `backend/app/api/valuation.py`
  - `GET /api/v1/valuation/indices` — 支持的指数列表及当前估值
  - `GET /api/v1/valuation/history/{index_code}` — 指数PE历史+分位数
  - `GET /api/v1/valuation/temperature` — 所有指数估值温度计
  - `GET /api/v1/valuation/dca-coefficient` — 定投系数建议

### 前端
- 新增 Valuation 页面
  - 估值温度计（仪表盘可视化）
  - PE 历史分位数图
  - 定投系数建议表

### 技术决策
- 复用 market_insight 已有的 index_kline API (已含 pe_ratio)
- 分位数使用 10 年历史数据
- 定投系数: 温度<20 → 1.5x, 20-40 → 1.2x, 40-60 → 1.0x, 60-80 → 0.8x, >80 → 0.5x
- 不新建数据模型，直接基于 fund_daily_prices 和 market_insight 现有数据计算
