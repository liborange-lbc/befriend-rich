# #12 数据导出 & 报表

## 概述
导出投资数据为 CSV/Excel 格式，生成投资报告。

## 设计

### 后端
- **API** `backend/app/api/export.py`
  - `GET /api/v1/export/portfolio-csv` — 导出持仓记录 CSV
  - `GET /api/v1/export/fund-stats-csv` — 导出基金风险指标 CSV
  - `GET /api/v1/export/report` — 生成 JSON 投资报告（前端可渲染）

### 前端
- 在 Settings 或各页面添加导出按钮
- 报告页面: 可视化投资报告（可截图/打印）

### 技术决策
- 使用 StreamingResponse + CSV 库（不需要额外依赖）
- 不生成 PDF（复杂且需要额外依赖如 weasyprint），而是生成结构化 JSON 报告
- 报告数据由前端渲染为可打印页面
