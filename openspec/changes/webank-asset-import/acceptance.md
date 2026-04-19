# 验收评审报告

## 评审概要
- 需求名称：webank-asset-import
- 评审时间：2026-04-19
- 评审结果：**通过**（附条件）

## 各阶段评审

### 需求阶段
- 状态：✅
- 说明：proposal.md 定义了 4 个子需求、5 个用户场景、11 条验收标准，范围清晰。验收标准逐条检查：
  1. Excel 上传导入 PortfolioRecord - 已实现（importer.py import_from_excel）
  2. AkShare 自动查询基金代码并创建 Fund - 已实现（fund_matcher.py find_or_create_fund）
  3. 新基金触发历史数据回填 - 已实现（fund_matcher.py 中调用 backfill）
  4. Claude API 自动分类 - 已实现（classifier.py classify_funds_with_ai）
  5. 从邮箱拉取按钮 - 已实现（email_puller.py + API pull-email 端点）
  6. 定时任务每天 9:00 - 已实现（scheduler/setup.py + jobs.py）
  7. 防重复导入 - 已实现（ImportLog 日期检查 + DuplicateImportError）
  8. 设置页配置 IMAP 凭据 - 已实现（Settings 页新增邮箱配置区域）
  9. 资产记录页展示历史数据 - 已实现（AssetRecords 页面 + RecordTable）
  10. 多维度自由分组 - 已实现（GroupSelector + group_by API 参数）
  11. 过滤功能 - 已实现（FilterBar + API 过滤参数）

### 设计阶段
- 状态：✅
- 说明：design.md 覆盖了架构、数据流、API 设计、前端组件结构、边界条件处理。代码抽查 5 个关键文件均与设计一致：
  - `backend/app/api/import_data.py`：5 个 API 端点（upload、pull-email、records、logs、group-dimensions）全部存在，签名与设计匹配
  - `backend/app/services/webank/importer.py`：全流程编排（Excel 解析 → 基金匹配 → AI 分类 → 持仓写入 → 快照生成 → ImportLog）完整实现
  - `backend/app/api/config.py`：SENSITIVE_KEYS 脱敏、_mask_sensitive 函数、PUT 跳过 ****** 均正确实现
  - `frontend/src/pages/AssetRecords/index.tsx`：组装了 ImportToolbar、FilterBar、GroupSelector、RecordTable 四个子组件，状态管理与设计一致
  - `frontend/src/components/Layout/AppLayout.tsx`：assetMenuItems 中已新增 `{ key: '/asset-records', icon: <FileTextOutlined />, label: '资产记录' }`，位置在资产总览和基金管理之间

### 开发阶段
- 状态：✅（附注意事项）
- 说明：
  - tasks.md 中 B1-B12、F1-F10 共 22 个开发任务全部勾选完成
  - 集成任务 I1-I3（前后端联调）未勾选，但 I4（构建验证）已通过
  - review.md 报告 0 个严重问题，3 个一般问题（均为非阻塞性），5 个建议
  - 代码质量：ImportResult 使用 frozen dataclass（不可变）、错误处理完善、文件组织清晰
  - 一般问题说明：
    - G1（pull-email statement_date 为 None）：前端通知会显示 "对账单日期: null"，体验不佳但不影响功能
    - G2（match_fund_by_name 全量加载 Fund）：当前基金数量级可接受
    - G3（force 删除不区分 source）：当前业务场景影响小

### 测试阶段
- 状态：✅
- 说明：
  - 后端 21 个测试用例全部通过，覆盖 API 端点、基金匹配、profit 计算、密码脱敏等核心场景
  - 前端 12 个 E2E 测试用例全部通过，覆盖页面渲染、导航、交互操作
  - 无失败用例

### 安全合规
- 状态：✅
- 说明：
  - IMAP 密码脱敏：GET /config 返回 ******，PUT 时 ****** 值跳过不更新（测试用例 #20、#21 验证通过）
  - SENSITIVE_KEYS 覆盖 imap_password、feishu_app_secret、anthropic_api_key
  - 文件上传校验 .xlsx 后缀
  - SQLAlchemy ORM 防 SQL 注入
  - zip 密码 090391 存储在 SystemConfig 表中（可通过设置页修改），非硬编码在代码中

## 最终结论

**通过**。需求的 11 条验收标准在代码层面全部满足，设计落地准确，测试全部通过，安全要求达标。3 个一般问题均为非阻塞性改进项。

附条件：集成任务 I1-I3（前后端联调）在 tasks.md 中未勾选。代码实现已完成，但实际前后端联调验证尚未记录。建议在部署前完成联调验证并更新 tasks.md。

## 建议

1. **短期修复（建议下一迭代）**：修复 G1（pull-email 响应中 statement_date 始终为 None），从 ImportLog 的 import_date 回填该字段
2. **性能优化**：G2 中 match_fund_by_name 全量加载 Fund 的问题，在基金数量增长后考虑改为 SQL 层面模糊查询
3. **代码规范**：S1（datetime.utcnow 已废弃）建议在 Python 3.12+ 环境中替换为 `datetime.now(UTC)`
4. **联调验证**：尽快完成 I1-I3 集成任务的实际验证并记录结果
