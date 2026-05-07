/**
 * 系统领域模型详细文档
 *
 * 用途：描述系统所有数据实体的字段定义、关系和业务含义。
 * 当用户提问涉及数据结构、字段含义、实体关系时加载此文档。
 */

export const DOMAIN_MODEL = `## 系统领域模型

### 基金（Fund）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| code | string | 基金代码（唯一），如 110011；无法匹配时生成 X{hash} 编码 |
| name | string | 基金名称 |
| currency | string | 币种：CNY / USD |
| data_source | string | 数据来源：akshare / yahoo / tushare |
| fee_rate | float | 费率(%) |
| is_active | bool | 是否激活（自动生成的标记为 false 待人工确认）|

关系：一个基金 → 多条每日价格、多条持仓记录、多个分类映射

### 每日价格（FundDailyPrice）
| 字段 | 类型 | 说明 |
|------|------|------|
| fund_id | int | 关联基金 |
| date | date | 日期 |
| close_price | float | 收盘价/净值 |
| ma_30 ~ ma_360 | float? | 30/60/120/250/360 日均线 |
| dev_30 ~ dev_360 | float? | 对应均线偏离度 |

唯一约束：(fund_id, date)

### 汇率（ExchangeRate）
| 字段 | 类型 | 说明 |
|------|------|------|
| date | date | 日期 |
| pair | string | 汇率对：USD/CNY、HKD/CNY |
| rate | float | 汇率值 |

### 分类体系（三层结构）
- **ClassModel**（分类模型）: 如"良田模型"、"全天候策略"、"地区分布"、"投资渠道"
  - 字段：id, name(唯一), description
- **ClassCategory**（分类类别）: 支持多级树结构（self-referential parent_id）
  - 字段：id, model_id, parent_id?, name, level, sort_order
  - 示例：良田模型 > 粮食作物 > 红利
- **FundClassMap**（基金分类映射）: 每个基金在每个模型下映射到一个叶子类别
  - 字段：id, fund_id, category_id, model_id

### 持仓记录（PortfolioRecord）
| 字段 | 类型 | 说明 |
|------|------|------|
| fund_id | int | 关联基金 |
| record_date | date | 记录日期 |
| amount | float | 原始币种持仓金额 |
| amount_cny | float | 折算人民币金额 |
| profit | float? | 收益（仅当数据源提供时有值，否则为 null）|

唯一约束：(fund_id, record_date)
数据频率：每周录入一次（通常来自微众银行对账单）

### 持仓快照（PortfolioSnapshot）
| 字段 | 类型 | 说明 |
|------|------|------|
| snapshot_date | date | 快照日期（唯一）|
| total_amount_cny | float | 当日总资产（人民币）|
| model_breakdown | JSON | 各分类模型下的资产明细 |

### 策略（Strategy）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 策略名称 |
| fund_id | int? | 关联基金（可选）|
| type | string | 策略类型：dca(定投) 等 |
| config | JSON | 策略参数 |
| alert_enabled | bool | 是否启用提醒 |
| alert_conditions | JSON[] | 提醒条件列表 |

### 回测结果（BacktestResult）
字段：strategy_id, fund_id, start_date, end_date, total_return, annual_return, sharpe_ratio, max_drawdown, volatility, win_rate, profit_loss_ratio, trade_log(JSON), equity_curve(JSON)

### 导入日志（ImportLog）
字段：import_date, source(excel_upload/email_pull), file_name, record_count, new_funds_count, status, error_message?, created_at

### 导入机制
- **Excel 上传**: 解析微众银行对账单 xlsx，提取"资产概览"页
- **邮箱拉取**: IMAP 连接 163 邮箱，搜索"微众银行电子版资产对账单"主题邮件，解密 zip → 解析 PDF
- **自动建仓**: AkShare 查询基金代码匹配，AI 自动分类到各分类模型`;
