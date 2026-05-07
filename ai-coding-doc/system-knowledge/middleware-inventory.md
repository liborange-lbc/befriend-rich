# Middleware & Infrastructure Inventory

## APScheduler (3.10.4)

Type: `BackgroundScheduler` (in-process, thread-based)

### Registered Jobs

| Job ID | Schedule | Function | Description |
|--------|----------|----------|-------------|
| `fetch_market_data` | Every hour (`:00`) | `job_fetch_market_data` | Fetch prices for all active funds + exchange rates |
| `strategy_check` | Configurable hours (default 9,12,14) | `job_strategy_check` | Evaluate strategy alert conditions |
| `webank_auto_import` | Daily 09:00 (conditional) | `job_webank_auto_import` | Pull WeBank statements from 163 email |
| `alipay_auto_import` | Daily 09:05 (conditional) | `job_alipay_auto_import` | Pull Alipay statements from 163 email |
| `weekly_data_completion` | Monday 08:00 | `job_weekly_data_completion` | Fill missing last-week portfolio data |
| `fetch_fund_holdings` | 1st of month 10:00 | `job_fetch_fund_holdings` | Fetch fund quarterly holding reports |
| `refresh_market_insight` | Monday 08:30 | `job_refresh_market_insight` | Refresh A-share market cap + index components |
| `auto_backup` | Daily 02:00 | `job_auto_backup` | SQLite DB backup, retain latest 30 |
| `guru_holdings_update` | 5th of month 10:30 | `job_guru_holdings_update` | Guru holdings from EastMoney + SEC EDGAR |

### Job Execution Recording

All jobs are wrapped with `@_record_run(job_id)` decorator that writes `JobRun` records:
- `started_at`, `finished_at`, `status` (success/failed), `summary`

### Conditional Jobs

- `webank_auto_import`: enabled only when `webank_auto_import_enabled` config is `"true"`
- `alipay_auto_import`: enabled only when `alipay_auto_import_enabled` config is `"true"`
- `strategy_check` hours: read from `scheduler_strategy_hours` config

## Feishu Notification

Location: `app/services/notification/feishu.py`

### Two Delivery Modes

1. **Webhook** (preferred): POST interactive card to configured webhook URL
2. **API**: Uses tenant access token + chat_id to send via Feishu Open API

### Configuration Keys

| Key | Purpose |
|-----|---------|
| `feishu_app_id` | Feishu app credentials |
| `feishu_app_secret` | Feishu app credentials |
| `feishu_webhook_url` | Webhook URL (takes priority over API) |

### Message Format

Interactive card with blue header template + markdown body. Used by strategy alert evaluator.

## Data Source Adapters

Location: `app/services/market_data/`

### Adapter Pattern

```
DataSourceAdapter (ABC)
  +-- TushareAdapter     (data_source="tushare")
  +-- YahooAdapter       (data_source="yahoo")
  +-- AkshareAdapter     (data_source="akshare")
```

Abstract interface:
- `fetch_daily_prices(code, start_date, end_date) -> DataFrame[date, close]`
- `fetch_exchange_rate(pair, start_date, end_date) -> DataFrame[date, rate]`

### Adapter Selection

Each `Fund` record has a `data_source` field. The `fetcher.py` module maps `data_source` string to adapter class via `ADAPTERS` dict.

## Email Pullers

### WeBank (`app/services/webank/`)
- `email_puller.py` - IMAP pull from 163 mailbox
- `importer.py` - Parse PDF statement + import portfolio records
- `classifier.py` - Match fund names to existing fund codes
- `fund_matcher.py` - Fuzzy fund matching

### Alipay (`app/services/alipay/`)
- `email_puller.py` - IMAP pull from 163 mailbox
- `parser.py` - Parse Alipay fund statement

## AI Assistant

Location: `app/services/assistant/`

- Uses Anthropic Claude API (`claude-sonnet-4-20250514`)
- Tool-use pattern: multi-round tool calls (max 3 rounds)
- Rate limited: 10 requests per minute (in-memory)
- System prompt defines "Meng Ke" (萌可) persona
- Tools defined in `app/services/assistant/tools.py`

## CORS Middleware

Configured in `main.py`:
- `allow_origins=["*"]`
- `allow_credentials=True`
- All methods and headers allowed
