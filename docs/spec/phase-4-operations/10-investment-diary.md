# #10 投资日记

## 概述
记录投资决策和市场背景，支持AI辅助生成总结。

## 设计

### 数据模型
- **新表** `diary_entries`
  - id, entry_date, title, content (Text), mood (enum), tags (Text/JSON)
  - created_at, updated_at

### 后端
- **模型** `backend/app/models/diary.py`
- **API** `backend/app/api/diary.py`
  - `GET /api/v1/diary` — 列表（分页+日期筛选+关键词搜索）
  - `POST /api/v1/diary` — 创建
  - `PUT /api/v1/diary/{id}` — 更新
  - `DELETE /api/v1/diary/{id}` — 删除
  - `POST /api/v1/diary/ai-summary` — AI 生成周/月投资总结

### 前端
- 新增 Diary 页面（资产管理模式）
  - 日记列表（时间线视图）
  - 创建/编辑表单
  - AI 总结按钮

### 技术决策
- mood 字段: bullish/neutral/bearish
- AI 总结复用现有 anthropic_api_key
- 简单的 Markdown 内容存储
