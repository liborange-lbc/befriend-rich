# #1 收益归因分析

## 概述
基于周快照数据，按多维度拆解收益来源。

## 设计

### 后端
- **服务** `backend/app/services/return_attribution_service.py`
  - 基于 portfolio_records 周快照计算:
    - 总收益 = 最新总金额 - 累计投入
    - 累计投入 = sum(weekly_investment)
    - 持仓收益 = 总收益（已含在 profit 字段中）
  - TWR: 链式周收益率 (排除新资金流入影响)
  - 按基金/分类/渠道维度的收益贡献
  - 基准对比（沪深300/中证500的同期收益率）

- **API** `backend/app/api/return_attribution.py`
  - `GET /api/v1/attribution/summary` — 总体收益归因
  - `GET /api/v1/attribution/by-fund` — 按基金的收益贡献
  - `GET /api/v1/attribution/by-category` — 按分类的收益贡献
  - `GET /api/v1/attribution/twr` — 时间加权收益率曲线

### 前端
- 新增 Attribution 页面
  - 总体收益概览卡片
  - 基金/分类收益贡献条形图
  - TWR 曲线 vs 基准

### 技术决策
- 使用周快照差值计算，精度为周级别
- TWR 公式: ∏(1 + R_t) - 1, R_t = (V_end - V_start - CF) / V_start
- 基准使用 fund_daily_prices 中已有的指数数据
