# #2 再平衡建议

## 概述
设定目标配置比例，计算偏离度，生成再平衡操作建议。

## 设计

### 数据模型
- **新表** `rebalance_targets` — 存储目标配置
  - category_id (FK → class_categories), target_pct (目标百分比)
  - model_id (FK → class_models)

### 后端
- **模型** `backend/app/models/rebalance.py`
- **服务** `backend/app/services/rebalance_service.py`
  - 读取当前各分类的实际持仓占比
  - 与目标对比计算偏离度
  - 生成再平衡操作建议（买入/卖出金额）
- **API** `backend/app/api/rebalance.py`
  - `GET /api/v1/rebalance/targets` — 当前目标配置
  - `POST /api/v1/rebalance/targets` — 设置目标配置
  - `GET /api/v1/rebalance/analysis` — 偏离分析+再平衡建议

### 前端
- 在资产管理模式下新增 Rebalance 页面
  - 目标配置编辑（各分类目标%）
  - 偏离度可视化（雷达图）
  - 操作建议列表

### 技术决策
- 基于良田模型分类体系（复用第一个 ClassModel）
- 偏离度 = |实际% - 目标%|
- 再平衡建议 = 目标金额 - 实际金额（正数买入，负数卖出）
