# #3 基金筛选/比较

## 概述
多基金对比（净值叠加、风险指标对比）、同类排名、关键指标看板。

## 设计

### 后端
- **新增服务** `backend/app/services/fund_stats_service.py`
  - 计算单基金风险指标: 年化收益率、最大回撤、夏普比率、波动率、近1/3/6/12月收益率
  - 基于 fund_daily_prices 数据计算
  - 夏普比率使用无风险利率 2.5%（中国国债收益率近似）

- **API** `backend/app/api/fund_compare.py`
  - `GET /api/v1/fund-compare/stats` — 所有活跃基金的风险指标
  - `GET /api/v1/fund-compare/prices` — 多基金归一化价格序列（叠加对比用）
  - `GET /api/v1/fund-compare/ranking` — 同类排名（按良田模型分类分组）

### 前端
- 新增 FundCompare 页面
  - 指标概览表格（排序/筛选）
  - 多基金选择 → 归一化净值叠加图
  - 同类排名面板

### 测试
- 后端: 风险指标计算（年化收益、最大回撤、夏普比率）
- 前端: TypeScript 编译
