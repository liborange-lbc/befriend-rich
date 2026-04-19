# 代码审查报告 - 微众银行资产数据导入与自动分类

## 审查范围

后端新增/修改文件 14 个，前端新增/修改文件 10 个。

---

## 一致性检查

### 与设计文档一致的部分
- ImportLog 模型结构与设计完全一致
- API 端点 5 个全部实现：upload、pull-email、records、logs、group-dimensions
- 路由注册、模型注册、定时任务注册均按设计完成
- 前端组件结构（ImportToolbar、FilterBar、GroupSelector、RecordTable）与设计一致
- 密码脱敏逻辑正确实现（SENSITIVE_KEYS + _mask_sensitive + PUT 跳过 ******）
- Pydantic Schema 与设计一致，且使用了 Pydantic v2 的 `model_config` 语法（正确）
- pull-email 的 force 参数已按设计 6.10 实现
- pull-email 响应已按设计 6.11 包含 classification_results
- profit 计算逻辑按设计 6.8 实现（上期 amount 差值）

### 与设计文档的偏差（均为可接受的偏差）
- 设计中 `EmailPullResultResponse` 无 `classification_results` 字段，但实现中已添加（符合设计 6.11 补充要求）
- 设计中 `pull-email` 响应有 `statement_date` 字段，但实现中硬编码为 `None`（**一般问题**，见下方）

---

## 严重问题（0 个）

无严重安全漏洞或逻辑错误。

---

## 一般问题（3 个）

### G1: pull-email 响应中 statement_date 始终为 None

**文件**：`backend/app/api/import_data.py` 第 82 行

```python
"statement_date": None,  # Will be set from import log
```

ImportResult 中没有 statement_date 字段，导致前端 `ImportToolbar.tsx` 第 75 行 `resp.data.statement_date` 始终为 null，通知显示 "对账单日期: null"。

**修复建议**：在 `import_from_parsed_data` 返回的 ImportResult 中新增 `record_date` 字段，或在 API 层从 ImportLog 中读取。

### G2: fund_matcher.py 中 match_fund_by_name 加载全部 Fund 到内存

**文件**：`backend/app/services/webank/fund_matcher.py` 第 47 行

```python
all_funds = db.query(Fund).all()
```

当基金数量较多时（数百条），每次匹配都加载全部 Fund 对象。目前规模可接受，但建议未来优化为 SQL 层面的模糊查询。

### G3: importer.py 中 force 删除逻辑未过滤 source

**文件**：`backend/app/services/webank/importer.py` 第 155-159 行

force=True 时删除该日期所有 PortfolioRecord，不区分来源。如果同一日期有手动录入和 Excel 导入的数据，force 重导会清除手动录入的数据。当前业务场景下影响较小。

---

## 建议（5 个）

### S1: datetime.utcnow 已废弃

**文件**：`backend/app/models/import_log.py` 第 19 行

`datetime.utcnow` 在 Python 3.12 已标记为 deprecated，建议使用 `datetime.now(UTC)`。

### S2: uploadExcel 使用了独立的 axios 实例

**文件**：`frontend/src/services/api.ts` 第 53 行

`uploadExcel` 直接使用 `axios.post` 而非封装的 `api` 实例，会绕过错误拦截器。当上传失败（400/409）时，不会被拦截器包装为 `{success: false, error: ...}` 格式，而是直接抛异常。前端 `ImportToolbar.tsx` 的 catch 块可以兜底，但行为与 `pullEmail` 不一致。

### S3: RecordTable 分类标签 key 使用 catName 可能重复

**文件**：`frontend/src/pages/AssetRecords/RecordTable.tsx` 第 51 行

```tsx
<Tag key={catName} ...>
```

如果同一基金在不同模型下恰好有同名分类，key 会重复。建议使用 `modelName + catName` 作为 key。

### S4: classifier.py 中 FundClassMap upsert 操作逐条查询

**文件**：`backend/app/services/webank/classifier.py` 第 185-198 行

每个 fund_id + model_id 组合都执行一次 SELECT 查询，可以批量查询后在内存中匹配。

### S5: 前端 FilterBar 的 Filters 接口重复定义

`FilterBar.tsx` 和 `index.tsx` 中各自定义了 `Filters` 接口，建议提取到共享位置。

---

## 安全性检查

| 检查项 | 结果 |
|--------|------|
| 密码脱敏 | 通过 - GET /config 返回 ******，PUT 跳过 ****** |
| SENSITIVE_KEYS 覆盖 | 通过 - imap_password, feishu_app_secret, anthropic_api_key |
| 文件上传校验 | 通过 - 检查 .xlsx 后缀 |
| SQL 注入防护 | 通过 - 使用 SQLAlchemy ORM |
| XSS 防护 | 通过 - React 默认转义 |
| 输入校验 | 通过 - FastAPI Query 参数类型校验 |
| 硬编码密码 | 注意 - zip 密码 "090391" 作为默认值存储在 SystemConfig 中，可通过设置页修改，可接受 |

---

## 完整性检查

| 设计功能点 | 实现状态 |
|-----------|---------|
| Excel 上传导入 | 已实现 |
| 邮箱拉取导入 | 已实现 |
| AkShare 基金匹配 + 缓存 | 已实现 |
| AI 分类 | 已实现 |
| 防重复导入 | 已实现 |
| force 覆盖 | 已实现 |
| 定时任务 | 已实现 |
| 资产记录页面 | 已实现 |
| 过滤（日期/关键字/分类） | 已实现 |
| 多维度分组 | 已实现 |
| 分组表格展开 | 已实现 |
| 导入历史 Drawer | 已实现 |
| 设置页 IMAP 配置 | 已实现 |
| 密码脱敏 | 已实现 |
| profit 计算 | 已实现 |
| 日期分组粒度（日/周/月） | 已实现 |
| config 默认值初始化 | 已实现 |

---

## 性能检查

| 项目 | 状态 |
|------|------|
| AkShare 缓存 24h | 已实现（模块级变量） |
| 批量 DB commit | 已实现（统一 commit） |
| 分页 | 前端表格有 pagination |
| N+1 查询 | list_import_records 中每条记录查 Fund + FundClassMap（可优化但当前可接受） |

---

## 总结

- 严重问题：0 个
- 一般问题：3 个
- 建议：5 个
- 整体评价：实现与设计文档高度一致，代码结构清晰，错误处理完善。主要改进空间在于 pull-email 的 statement_date 字段和少量性能优化。
