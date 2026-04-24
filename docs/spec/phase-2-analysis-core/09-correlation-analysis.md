# #9 相关性分析

## 概述
基金间相关性矩阵热力图、隐性重叠识别（基于持仓穿透）、组合分散度评分。

## 设计

### 后端
- **新增服务** `backend/app/services/correlation_service.py`
  - 计算基金间收益率相关性矩阵（Pearson）
  - 基于 fund_holdings 计算持仓重叠度
  - 组合分散度评分（平均相关系数的反指标）

- **API** `backend/app/api/correlation.py`
  - `GET /api/v1/correlation/matrix` — 收益率相关性矩阵
  - `GET /api/v1/correlation/overlap` — 持仓重叠矩阵
  - `GET /api/v1/correlation/diversification-score` — 分散度评分

### 前端
- 新增 Correlation 页面（挂在 market menu 下）
  - 相关性热力图（ECharts heatmap）
  - 持仓重叠表
  - 分散度评分卡

### 技术决策
- 相关性计算使用最近1年日频收益率
- 重叠度 = 两基金共同持股数量 / 两基金持股并集数量（Jaccard）
- 分散度 = 1 - 平均相关系数
