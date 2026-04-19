# 实现任务

## 后端任务

### 数据模型与基础设施
- [x] 任务B1：创建 `backend/app/models/import_log.py` - ImportLog 模型，并在 `__init__.py` 中注册
- [x] 任务B2：创建 `backend/app/schemas/import_data.py` - 所有 Pydantic Schema（ImportResultResponse, ImportRecordResponse, GroupedResult, GroupDimension 等）
- [x] 任务B3：更新 `backend/requirements.txt` - 新增 pdfplumber, openpyxl 依赖

### 核心服务
- [x] 任务B4：创建 `backend/app/services/webank/__init__.py` 和 `backend/app/services/webank/fund_matcher.py` - 基金名称匹配 + AkShare 代码查询（match_fund_by_name, lookup_fund_code_via_akshare, find_or_create_fund）
- [x] 任务B5：创建 `backend/app/services/webank/classifier.py` - AI 分类服务（classify_funds_with_ai），包含 Claude API 调用和 FundClassMap 批量创建
- [x] 任务B6：创建 `backend/app/services/webank/importer.py` - 全流程导入编排（import_from_excel, import_from_parsed_data），包含 Excel 解析、基金匹配、分类、持仓写入、快照生成、ImportLog 记录
- [x] 任务B7：创建 `backend/app/services/webank/email_puller.py` - IMAP 邮箱拉取服务（pull_latest_statement），复用 webank-statement-to-excel 的 PDF 解析逻辑

### API 端点
- [x] 任务B8：创建 `backend/app/api/import_data.py` - 5 个 API 端点（upload, pull-email, records, logs, group-dimensions），并在 `main.py` 中注册路由
- [x] 任务B9：实现 GET /import/records 的分组查询逻辑 - 支持 group_by 参数的多维度自由组合分组，返回分组汇总和明细

### 安全与配置
- [x] 任务B10：修改现有 config API，对 SENSITIVE_KEYS（imap_password, feishu_app_secret）做脱敏处理，返回 `******` 而非明文；PUT 时 value 为 `******` 则跳过不更新
- [x] 任务B11：在应用启动或服务初始化时，确保 SystemConfig 表中存在 6 个新增邮箱配置项的默认值（imap_email, imap_password, imap_host, webank_zip_password, webank_auto_import_enabled, webank_auto_import_cron）

### 定时任务
- [x] 任务B12：修改 `backend/app/scheduler/jobs.py` 新增 job_webank_auto_import 函数，修改 `setup.py` 注册每天 9:00 定时任务

## 前端任务

### 类型与API层
- [x] 任务F1：修改 `frontend/src/types/index.ts` - 新增 ImportResult, EmailPullResult, ImportLog, ImportRecord, GroupedRecordResult, GroupDimension, RecordSummary 类型
- [x] 任务F2：修改 `frontend/src/services/api.ts` - 新增 uploadExcel, pullEmail, getImportRecords, getImportLogs, getGroupDimensions 函数

### 页面组件
- [x] 任务F3：创建 `frontend/src/pages/AssetRecords/ImportToolbar.tsx` - 导入操作栏（上传Excel弹窗 + 从邮箱拉取按钮 + 导入历史Drawer）
- [x] 任务F4：创建 `frontend/src/pages/AssetRecords/FilterBar.tsx` - 过滤条件栏（日期范围、基金搜索、分类模型筛选）
- [x] 任务F5：创建 `frontend/src/pages/AssetRecords/GroupSelector.tsx` - 分组维度选择器（CheckableTag 自由组合）
- [x] 任务F6：创建 `frontend/src/pages/AssetRecords/RecordTable.tsx` - 数据表格（无分组明细模式 + 分组展开模式，底部汇总行）
- [x] 任务F7：创建 `frontend/src/pages/AssetRecords/index.tsx` - 资产记录主页面，组装 ImportToolbar + FilterBar + GroupSelector + RecordTable，管理状态和数据流

### 路由与导航
- [x] 任务F8：修改 `frontend/src/App.tsx` 新增 /asset-records 路由
- [x] 任务F9：修改 `frontend/src/components/Layout/AppLayout.tsx` 在 Asset 菜单中新增"资产记录"菜单项

### 设置页
- [x] 任务F10：修改 `frontend/src/pages/Settings/index.tsx` 新增"邮箱配置"区域（imap_email, imap_password 配置项）

## 集成任务
- [ ] 任务I1：前后端联调 - Excel 上传导入全流程（文件上传 → 解析 → 匹配 → 分类 → 录入 → 页面刷新）
- [ ] 任务I2：前后端联调 - 邮箱拉取全流程（点击按钮 → IMAP 连接 → 解析 → 导入 → 页面刷新）
- [ ] 任务I3：前后端联调 - 分组查询（选择维度 → 后端分组 → 前端渲染分组表格）
- [x] 任务I4：构建验证 - 后端 pytest 通过 + 前端 tsc --noEmit + vite build 通过
