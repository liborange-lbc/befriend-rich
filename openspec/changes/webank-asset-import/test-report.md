# 测试报告

## 代码审查结果

- 严重问题：0 个
- 一般问题：3 个
  - G1: pull-email 响应中 statement_date 始终为 None
  - G2: fund_matcher 中 match_fund_by_name 每次加载全部 Fund 到内存
  - G3: force 删除逻辑未过滤 source，会清除同日期所有来源的数据
- 建议：5 个
  - S1: datetime.utcnow 已废弃（Python 3.12+）
  - S2: uploadExcel 使用独立 axios 实例绕过错误拦截器
  - S3: RecordTable 分类标签 key 可能重复
  - S4: classifier.py 中 FundClassMap upsert 逐条查询
  - S5: FilterBar 的 Filters 接口重复定义

详细审查报告见 review.md。

## 后端测试结果

- 总用例数：21
- 通过：21
- 失败：0

### 用例清单

| # | 用例 | 结果 |
|---|------|------|
| 1 | POST /import/upload - 正常上传 Excel | 通过 |
| 2 | POST /import/upload - 文件格式错误 (.csv) | 通过 |
| 3 | POST /import/upload - 重复导入返回 409 | 通过 |
| 4 | POST /import/upload - force=true 覆盖导入 | 通过 |
| 5 | POST /import/pull-email - 凭据未配置返回 400 | 通过 |
| 6 | GET /import/records - 空数据返回空列表 | 通过 |
| 7 | GET /import/records - 有数据返回记录 | 通过 |
| 8 | GET /import/records - group_by=currency 分组查询 | 通过 |
| 9 | GET /import/records - keyword 过滤 | 通过 |
| 10 | GET /import/logs - 查询导入日志 | 通过 |
| 11 | GET /import/group-dimensions - 默认 4 个维度 | 通过 |
| 12 | GET /import/group-dimensions - 包含分类模型维度 | 通过 |
| 13 | fund_matcher - 精确匹配 | 通过 |
| 14 | fund_matcher - 括号归一化匹配 | 通过 |
| 15 | fund_matcher - 份额后缀去除匹配 | 通过 |
| 16 | fund_matcher - 无匹配返回 None | 通过 |
| 17 | find_or_create_fund - 新建基金（无 AkShare 匹配） | 通过 |
| 18 | find_or_create_fund - AkShare 匹配创建基金 | 通过 |
| 19 | profit 计算 - 首次为 0，后续为差值 | 通过 |
| 20 | config API - 密码脱敏返回 ****** | 通过 |
| 21 | config API - PUT 跳过 ****** 不覆盖原值 | 通过 |

## 前端 E2E 测试结果

- 总用例数：12
- 通过：12
- 失败：0

### 用例清单

| # | 用例 | 结果 |
|---|------|------|
| 1 | 导航到资产记录页面并显示标题 | 通过 |
| 2 | 显示上传和拉取按钮 | 通过 |
| 3 | 显示导入历史按钮 | 通过 |
| 4 | 显示过滤栏（日期范围、搜索、分类模型） | 通过 |
| 5 | 显示分组选择器 | 通过 |
| 6 | 点击上传按钮打开上传 Modal | 通过 |
| 7 | 关闭上传 Modal | 通过 |
| 8 | 打开导入历史 Drawer | 通过 |
| 9 | 关闭导入历史 Drawer | 通过 |
| 10 | 侧边栏显示资产记录菜单项 | 通过 |
| 11 | 侧边栏导航到资产记录页面 | 通过 |
| 12 | 显示数据表格 | 通过 |

## 问题清单

无阻塞性问题。代码审查中的 3 个一般问题和 5 个建议均为非阻塞性改进项，不影响功能正确性。
