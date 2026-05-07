# Data Dictionary

## Database

- Engine: SQLite
- File: `data/fundasset.db`
- PRAGMA: `journal_mode=WAL`, `foreign_keys=ON`
- Connection: `check_same_thread=False`

---

## Table: `funds`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | autoincrement | PK |
| code | String(20) | NO | | UNIQUE, INDEXED |
| name | String(100) | NO | | |
| currency | String(10) | NO | `"CNY"` | CNY, USD, HKD |
| data_source | String(20) | NO | `"tushare"` | tushare, yahoo, akshare |
| fee_rate | Float | NO | `0.0` | Total holding fee rate |
| management_fee | Float | YES | | Management fee % |
| custody_fee | Float | YES | | Custody fee % |
| service_fee | Float | YES | | Sales service fee % |
| is_active | Boolean | NO | `True` | |
| holding_source | String(20) | YES | | Proxy fund code for holdings |

---

## Table: `fund_daily_prices`

Unique constraint: `(fund_id, date)`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| fund_id | Integer | NO | FK -> funds.id CASCADE, INDEXED |
| date | Date | NO | INDEXED |
| close_price | Float | NO | |
| ma_30 .. ma_360 | Float | YES | Moving averages (30,60,90,120,180,250,360) |
| dev_30 .. dev_360 | Float | YES | Standard deviations (same windows) |

---

## Table: `exchange_rates`

Unique constraint: `(date, pair)`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | | PK |
| date | Date | NO | | INDEXED |
| pair | String(10) | NO | `"USD/CNY"` | e.g. USD/CNY, HKD/CNY |
| rate | Float | NO | | |

---

## Table: `portfolio_records`

Unique constraint: `(fund_id, channel, record_date)`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | | PK |
| fund_id | Integer | NO | | FK -> funds.id CASCADE, INDEXED |
| record_date | Date | NO | | INDEXED, always Monday of ISO week |
| amount | Float | NO | | Original currency amount |
| amount_cny | Float | NO | | CNY-converted amount |
| profit | Float | YES | | Cumulative profit |
| weekly_investment | Float | YES | | Weekly DCA amount |
| channel | String(20) | NO | `"微众银行"` | |

---

## Table: `portfolio_snapshots`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | | PK |
| snapshot_date | Date | NO | | UNIQUE, INDEXED |
| total_amount_cny | Float | NO | | |
| model_breakdown | Text | NO | `"{}"` | JSON: model -> category -> amount |

---

## Table: `class_models`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| name | String(100) | NO | UNIQUE |
| description | Text | NO | Default `""` |

---

## Table: `class_categories`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| model_id | Integer | NO | FK -> class_models.id CASCADE |
| parent_id | Integer | YES | FK -> class_categories.id CASCADE (self-ref) |
| name | String(100) | NO | |
| level | Integer | NO | Default `1` |
| sort_order | Integer | NO | Default `0` |

---

## Table: `fund_class_maps`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| fund_id | Integer | NO | FK -> funds.id CASCADE |
| category_id | Integer | NO | FK -> class_categories.id CASCADE |
| model_id | Integer | NO | FK -> class_models.id CASCADE |

---

## Table: `strategies`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | | PK |
| name | String(100) | NO | | |
| fund_id | Integer | YES | | FK -> funds.id SET NULL |
| type | String(30) | NO | `"dca"` | Strategy type |
| config | Text | NO | `"{}"` | JSON parameters |
| alert_enabled | Boolean | NO | `True` | |
| alert_conditions | Text | NO | `"[]"` | JSON alert rules |
| is_active | Boolean | NO | `True` | |

---

## Table: `backtest_results`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| strategy_id | Integer | NO | FK -> strategies.id CASCADE |
| fund_id | Integer | NO | FK -> funds.id CASCADE |
| start_date | Date | NO | |
| end_date | Date | NO | |
| total_return | Float | YES | |
| annual_return | Float | YES | |
| sharpe_ratio | Float | YES | |
| max_drawdown | Float | YES | |
| volatility | Float | YES | |
| win_rate | Float | YES | |
| profit_loss_ratio | Float | YES | |
| trade_log | Text | NO | JSON array, default `"[]"` |
| equity_curve | Text | NO | JSON array, default `"[]"` |

---

## Table: `alert_logs`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| strategy_id | Integer | NO | FK -> strategies.id CASCADE |
| fund_id | Integer | YES | FK -> funds.id SET NULL |
| triggered_at | String(30) | NO | ISO timestamp string |
| condition_desc | Text | NO | Default `""` |
| current_values | Text | NO | JSON, default `"{}"` |
| notified | Boolean | NO | Default `False` |

---

## Table: `fund_holdings`

Unique constraint: `(fund_id, quarter, stock_code)`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| fund_id | Integer | NO | FK -> funds.id CASCADE, INDEXED |
| quarter | String(20) | NO | INDEXED, e.g. "2024Q4" |
| stock_code | String(20) | NO | |
| stock_name | String(100) | NO | |
| holding_ratio | Float | YES | % of NAV |
| holding_shares | Float | YES | Shares (万股) |
| holding_value | Float | YES | Value (万元) |
| disclosure_date | String(30) | YES | |

---

## Table: `rebalance_targets`

Unique constraint: `(model_id, category_id)`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| model_id | Integer | NO | FK -> class_models.id CASCADE, INDEXED |
| category_id | Integer | NO | FK -> class_categories.id CASCADE, INDEXED |
| target_pct | Float | NO | Default `0.0` |

---

## Table: `market_stock`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| code | String(10) | NO | INDEXED |
| name | String(50) | NO | |
| exchange | Integer | NO | 1=SH, 0=SZ/BJ |
| market_cap | Float | NO | Unit: yuan |
| industry | String(50) | YES | Level-1 industry |
| snapshot_date | Date | NO | INDEXED |

---

## Table: `market_index_component`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| index_code | String(10) | NO | INDEXED |
| stock_code | String(10) | NO | |
| snapshot_date | Date | NO | INDEXED |

---

## Table: `gurus`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| name | String(100) | NO | |
| name_en | String(100) | YES | |
| slug | String(100) | NO | UNIQUE |
| category | String(20) | YES | china_fund / asia / north_america |
| description | Text | YES | |
| num_holdings | Integer | YES | Default `0` |
| num_trades | Integer | YES | Default `0` |

---

## Table: `guru_holdings`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| guru_id | Integer | YES | FK -> gurus.id |
| stock_code | String(20) | YES | |
| stock_name | String(100) | YES | |
| position_change | String(20) | YES | |
| trade_impact_pct | String(20) | YES | |
| shares | String(50) | YES | |
| value | String(50) | YES | |
| weight_pct | String(20) | YES | |
| ownership_pct | String(20) | YES | |
| sector | String(80) | YES | |
| market_cap | String(50) | YES | |
| return_3m_pct | String(20) | YES | |
| return_ytd_pct | String(20) | YES | |

---

## Table: `guru_trades`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| guru_id | Integer | YES | FK -> gurus.id |
| stock_code | String(20) | YES | |
| stock_name | String(100) | YES | |
| action | String(50) | YES | |
| shares_changed | String(50) | YES | |
| price | String(50) | YES | |
| value | String(50) | YES | |
| trade_date | String(20) | YES | |
| report_date | String(20) | YES | |
| current_shares | String(50) | YES | |

---

## Table: `guru_stocks`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| code | String(20) | YES | UNIQUE |
| name | String(100) | YES | |
| market | String(10) | YES | A / HK / US / TW |
| sector | String(80) | YES | |
| guru_count | Integer | YES | Default `0` |

---

## Table: `system_config`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| key | String(100) | NO | UNIQUE, INDEXED |
| value | Text | NO | Default `""` |
| category | String(50) | NO | Default `"general"` |
| description | String(200) | NO | Default `""` |

---

## Table: `job_runs`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | Integer | NO | PK |
| job_id | String(50) | NO | INDEXED |
| started_at | DateTime | NO | |
| finished_at | DateTime | YES | |
| status | String(20) | NO | success / failed |
| summary | Text | YES | |

---

## Table: `import_logs`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | | PK |
| import_date | Date | NO | | INDEXED |
| source | String(20) | NO | | |
| file_name | String(200) | NO | | |
| record_count | Integer | NO | `0` | |
| new_funds_count | Integer | NO | `0` | |
| status | String(20) | NO | `"success"` | |
| error_message | Text | YES | | |
| weekly_investment_total | Float | YES | | |
| created_at | DateTime | NO | `utcnow` | |

---

## Table: `diary_entries`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | Integer | NO | | PK |
| entry_date | Date | NO | | INDEXED |
| title | String(200) | NO | | |
| content | Text | NO | `""` | |
| mood | String(20) | YES | | bullish / neutral / bearish |
| tags | Text | NO | `"[]"` | JSON array of strings |
| created_at | DateTime | NO | `now` | |
| updated_at | DateTime | NO | `now` | Auto-update on change |
