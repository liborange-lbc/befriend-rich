# Domain Model

## Entity Summary (20 models, 20 tables)

### Core Domain

| Entity | Table | Description |
|--------|-------|-------------|
| Fund | `funds` | Fund master data (code, name, currency, data source, fees) |
| FundDailyPrice | `fund_daily_prices` | Daily close prices + moving averages + standard deviations |
| ExchangeRate | `exchange_rates` | Daily exchange rates (USD/CNY, HKD/CNY) |
| PortfolioRecord | `portfolio_records` | Weekly fund holdings by amount, per channel |
| PortfolioSnapshot | `portfolio_snapshots` | Point-in-time total portfolio value + model breakdown |

### Classification

| Entity | Table | Description |
|--------|-------|-------------|
| ClassModel | `class_models` | Classification model (e.g., "asset class", "geography") |
| ClassCategory | `class_categories` | Hierarchical category tree (self-referencing parent_id) |
| FundClassMap | `fund_class_maps` | Many-to-many: fund <-> category under a specific model |

### Strategy & Backtest

| Entity | Table | Description |
|--------|-------|-------------|
| Strategy | `strategies` | Investment strategy definition (type, config JSON, alert rules) |
| BacktestResult | `backtest_results` | Backtest run results (returns, sharpe, drawdown, trade log) |
| AlertLog | `alert_logs` | Strategy alert trigger history |

### Market Insight

| Entity | Table | Description |
|--------|-------|-------------|
| MarketStock | `market_stock` | A-share market cap snapshots (weekly refresh) |
| MarketIndexComponent | `market_index_component` | Index constituent stocks (weekly refresh) |

### Fund Holdings (X-Ray)

| Entity | Table | Description |
|--------|-------|-------------|
| FundHolding | `fund_holdings` | Quarterly fund top-10 stock holdings |

### Rebalance

| Entity | Table | Description |
|--------|-------|-------------|
| RebalanceTarget | `rebalance_targets` | Target allocation percentages per model category |

### Guru

| Entity | Table | Description |
|--------|-------|-------------|
| Guru | `gurus` | Investment guru profiles (name, slug, category) |
| GuruHolding | `guru_holdings` | Current guru stock positions |
| GuruTrade | `guru_trades` | Guru trade history |
| GuruStock | `guru_stocks` | Aggregated stock-level guru data |

### System

| Entity | Table | Description |
|--------|-------|-------------|
| SystemConfig | `system_config` | Key-value configuration store |
| JobRun | `job_runs` | Scheduler job execution history |
| ImportLog | `import_logs` | Data import audit trail |
| DiaryEntry | `diary_entries` | Investment diary entries |

## ER Diagram (Text)

```
funds ──1:N──> fund_daily_prices
funds ──1:N──> portfolio_records
funds ──1:N──> fund_holdings
funds ──1:N──> fund_class_maps
funds ──0:N──> strategies (nullable FK)
funds ──0:N──> backtest_results

class_models ──1:N──> class_categories
class_categories ──0:N──> class_categories (self-ref parent_id)
class_models ──1:N──> fund_class_maps
class_categories ──1:N──> fund_class_maps
class_models ──1:N──> rebalance_targets
class_categories ──1:N──> rebalance_targets

strategies ──1:N──> backtest_results
strategies ──1:N──> alert_logs

gurus ──1:N──> guru_holdings  (selectin lazy load)
gurus ──1:N──> guru_trades    (selectin lazy load)

portfolio_records  (unique: fund_id + channel + record_date)
fund_daily_prices  (unique: fund_id + date)
exchange_rates     (unique: date + pair)
fund_holdings      (unique: fund_id + quarter + stock_code)
rebalance_targets  (unique: model_id + category_id)

-- Standalone tables (no FK relationships) --
portfolio_snapshots
market_stock
market_index_component
guru_stocks
system_config
job_runs
import_logs
diary_entries
```

## Key Relationships

1. **Fund** is the central entity -- most other tables reference `funds.id` via FK with `CASCADE` delete
2. **ClassModel -> ClassCategory** uses `relationship` with `cascade="all, delete-orphan"` and `back_populates`
3. **ClassCategory** is self-referencing for hierarchical tree (`parent_id` -> `class_categories.id`)
4. **Guru -> GuruHolding/GuruTrade** uses `selectin` eager loading
5. **Strategy -> Fund** FK uses `SET NULL` on delete (strategy survives fund deletion)

## JSON-in-Text Columns

Several models store structured data as JSON text:
- `Strategy.config` - strategy parameters (JSON object)
- `Strategy.alert_conditions` - alert rules (JSON array)
- `BacktestResult.trade_log` - trade history (JSON array)
- `BacktestResult.equity_curve` - equity points (JSON array)
- `AlertLog.current_values` - snapshot of values at trigger (JSON object)
- `PortfolioSnapshot.model_breakdown` - category amounts (JSON object)
- `DiaryEntry.tags` - tag list (JSON array)
