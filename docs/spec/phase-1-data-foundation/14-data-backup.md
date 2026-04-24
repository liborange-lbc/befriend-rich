# #14 数据备份

## 概述
为 SQLite 数据库提供自动和手动备份能力，防止数据丢失。

## 设计

### 后端
- **备份服务** `backend/app/services/backup_service.py`
  - 使用 SQLite 的 `VACUUM INTO` 命令创建一致性备份（不锁表）
  - 备份目录: `backend/data/backups/`
  - 文件命名: `fundasset_YYYYMMDD_HHMMSS.db`
  - 保留策略: 保留最近 N 个备份（默认30），自动清理旧备份

- **API** `backend/app/api/backup.py`
  - `POST /api/v1/backup/create` — 手动触发备份
  - `GET /api/v1/backup/list` — 列出所有备份（文件名、大小、时间）
  - `POST /api/v1/backup/restore` — 从指定备份恢复（危险操作，需确认参数）
  - `DELETE /api/v1/backup/{filename}` — 删除指定备份

- **定时任务** — 每天凌晨 2:00 自动备份

- **SystemConfig 新增**
  - `backup_enabled`: true/false（默认 true）
  - `backup_retention_count`: 保留数量（默认 30）
  - `backup_cron_hour`: 备份小时（默认 2）

### 前端
- 在 Settings 页面新增「数据备份」卡片
  - 显示备份列表（时间、大小）
  - 手动备份按钮
  - 恢复按钮（带二次确认）
  - 删除按钮

### 测试
- 后端: 备份创建、列表、清理策略、恢复
- 前端: TypeScript 编译通过

## 技术决策
- 使用 `VACUUM INTO` 而非文件复制，确保备份文件完整性
- 不备份到云存储（当前为个人项目，本地备份足够）
- WAL 文件不需要单独备份，`VACUUM INTO` 会将 WAL 合并
