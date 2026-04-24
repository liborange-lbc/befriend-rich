# #6 数据源健康监控

## 概述
监控所有外部数据源的健康状态和数据质量，提供拉取历史和失败告警。

## 设计

### 后端
- **数据模型**: 复用现有 `job_runs` 表（已有 job_id, status, summary, started_at, finished_at）
- **新增服务** `backend/app/services/data_health_service.py`
  - 汇总各 job 的最近运行状态
  - 检查数据覆盖率（每个活跃基金最近价格日期 vs 今天）
  - 检查异常值（价格为0或负数、连续多天价格相同）
  
- **API** `backend/app/api/data_health.py`
  - `GET /api/v1/data-health/overview` — 所有数据源的健康概览
  - `GET /api/v1/data-health/fund-coverage` — 每个基金的数据覆盖情况
  - `GET /api/v1/data-health/job-history` — 最近任务执行历史（复用 scheduler API 但加工）

### 前端
- 新增 DataHealth 页面（挂在设置/工具下或 Dashboard 可跳转）
  - 数据源状态卡片（绿/黄/红灯）
  - 基金数据覆盖率表格
  - 任务执行历史时间线

### 测试
- 后端: 健康状态计算、覆盖率统计
- 前端: TypeScript 编译通过
