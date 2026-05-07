/**
 * 系统 API 接口文档
 *
 * 用途：列出所有后端 API 端点的路径、参数和返回格式。
 * 当用户提问涉及数据查询、操作指引或需要调用接口时加载此文档。
 */

export const API_REFERENCE = `## 数据获取 API（基础路径: /api/v1）

### 基金管理 /funds
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | / | keyword, is_active, page, page_size(1-100) | FundResponse[] + meta{total,page,page_size} |
| GET | /{fund_id} | - | FundResponse |
| POST | / | code, name, currency, data_source, fee_rate | FundResponse |
| PUT | /{fund_id} | 同上(均可选) | FundResponse |
| DELETE | /{fund_id} | - | {deleted} |
| GET | /{fund_id}/backfill-status | - | 回填任务状态 |

### 持仓数据 /portfolio
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | /records/dates | - | string[] 所有有记录的日期 |
| GET | /records/latest | target_date? | PortfolioRecord[] + meta{latest_date} |
| GET | /records | start_date?, end_date?, fund_id? | PortfolioRecord[] |
| POST | /records | fund_id, record_date, amount, profit? | PortfolioRecord |
| POST | /records/batch | records[] | {message} |
| PUT | /records/{id} | amount?, profit? | PortfolioRecord |
| GET | /breakdown | target_date? | {模型名: {类别名: 金额}} |
| GET | /trend | start_date?, end_date? | {date, total}[] |
| GET | /top5 | target_date? | {rank, fund_name, amount_cny, percentage, profit}[] |
| GET | /snapshots | start_date?, end_date? | PortfolioSnapshot[] |
| POST | /snapshots/generate | snapshot_date | 快照结果 |

### 分类查询 /classification
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | /models | - | ClassModel[] |
| POST | /models | name, description | ClassModel |
| PUT | /models/{id} | name?, description? | ClassModel |
| DELETE | /models/{id} | - | {deleted} |
| GET | /categories/tree | model_id | ClassCategory[] (递归含 children) |
| GET | /categories | model_id | ClassCategory[] (扁平) |
| POST | /categories | model_id, parent_id?, name, sort_order? | ClassCategory |
| PUT | /categories/{id} | name?, parent_id?, sort_order? | ClassCategory |
| DELETE | /categories/{id} | - | {deleted} |
| GET | /mappings | fund_id?, model_id? | FundClassMap[] |
| POST | /mappings | fund_id, category_id, model_id | FundClassMap |
| DELETE | /mappings/{id} | - | {deleted} |
| POST | /auto-classify | - | {classified, message} |

### 市场数据 /analysis & /dashboard
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | /analysis/prices/{fund_id} | start_date?, end_date? | FundDailyPrice[] |
| GET | /analysis/deviation-summary | - | DeviationSummary[] |
| GET | /dashboard/overview | - | {total_amount_cny, change_amount, change_pct, usd_cny_rate, hkd_cny_rate} |
| GET | /dashboard/fund-quotes | - | {fund_id, code, name, close_price, change_pct, date}[] |
| GET | /dashboard/alerts/recent | - | AlertLog[] |

### 汇率 /market-data/exchange-rate
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | /history | pair?(USD/CNY), start_date?, end_date? | {date, rate}[] |
| POST | /fetch | target_date? | {rate} |
| POST | /backfill | pair?(USD/CNY) | {message, count} |

### 导入管理 /import
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| POST | /upload | file(.xlsx), record_date, force? | ImportResult |
| POST | /pull-email | force? | ImportResult + email_found |
| GET | /records | start_date?, end_date?, fund_id?, keyword?, model_id?, category_id?, group_by? | 记录列表或分组结果 |
| PUT | /records/{id} | amount, profit?, fund_code?, fund_name? | {updated, id} |
| DELETE | /records/{id} | - | {deleted, id} |
| POST | /records/batch-delete | ids[] | {deleted} |
| GET | /logs | limit?(20) | ImportLog[] |
| GET | /group-dimensions | - | {key, label, type}[] |

### 策略 /strategy
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | / | is_active? | Strategy[] |
| POST | / | name, fund_id?, type, config, alert_enabled, alert_conditions | Strategy |
| GET | /{id} | - | Strategy |
| PUT | /{id} | 同上(均可选) | Strategy |
| DELETE | /{id} | - | {deleted} |
| GET | /alerts/recent | limit?(20) | AlertLog[] |

### 回测 /backtest
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| POST | /run | strategy_id, fund_id, start_date, end_date | BacktestResult |
| GET | /results | strategy_id? | BacktestResult[] |
| GET | /results/{id} | - | BacktestResult |

### 系统配置 /config
| 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|
| GET | / | - | ConfigItem[] (敏感字段值脱敏) |
| PUT | / | configs: {key: value} | {updated} |`;
