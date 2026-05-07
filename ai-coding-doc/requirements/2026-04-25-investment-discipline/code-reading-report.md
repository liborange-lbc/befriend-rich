# Code Reading Report: Investment Discipline System

> Date: 2026-04-25
> Scope: Backend models, APIs, services; Frontend patterns
> Purpose: Identify integration points, reuse opportunities, and constraints for the new Investment Discipline feature (5 modules: Plan, Alert, TradeEval, Constraint, Report)

---

## 1. Module Dependency Diagram

```
                         ┌──────────────┐
                         │   main.py    │
                         │  (FastAPI)   │
                         └──────┬───────┘
                                │ include_router
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   api/portfolio  api/strategy  api/guru  api/assistant  api/...
        │           │           │           │
        ▼           ▼           ▼           ▼
   models/        models/     models/    services/
   portfolio    strategy      guru      assistant/
        │           │                    tools.py
        ▼           ▼                       │
   schemas/      schemas/                   ▼
   portfolio    strategy              Anthropic Claude API
        │           │
        ▼           ▼
   services/     services/
   portfolio/    strategy/
   snapshot.py   evaluator.py ──► services/notification/feishu.py
                                          │
                                          ▼
                                    Feishu Webhook / API
        
   scheduler/setup.py ──► scheduler/jobs.py ──► all service modules
                                │
                                ▼
                         APScheduler (BackgroundScheduler)
```

---

## 2. Key Call Chains

### 2.1 Portfolio Module

```
POST /api/v1/portfolio/records/batch
  → api/portfolio.py::batch_create_records()
    → Fund.query(fund_id) → get currency
    → get_latest_rate(db) → convert USD→CNY
    → upsert PortfolioRecord
    → generate_snapshot(db, date)
      → _build_model_breakdown(db, records)
      → upsert PortfolioSnapshot
```

**Key Models:**
- `PortfolioRecord`: fund_id, record_date(weekly Monday), amount, amount_cny, profit, weekly_investment, channel
  - Unique: (fund_id, channel, record_date)
- `PortfolioSnapshot`: snapshot_date(unique), total_amount_cny, model_breakdown(JSON text)
- `Fund`: id, code, name, currency(CNY/USD), data_source, fee_rate, is_active

**Patterns:**
- Records are weekly snapshots (Monday-based), NOT transaction-level
- Currency conversion happens at record time via `get_latest_rate()`
- No transaction/trade log exists yet -- portfolio is asset-amount-based, not trade-based

### 2.2 Strategy + Alert Module

```
Scheduler job_strategy_check (cron: 9,12,14 o'clock)
  → jobs.py::job_strategy_check()
    → strategy/evaluator.py::run_strategy_check(db)
      → query all active + alert_enabled strategies
      → for each: _check_strategy(db, strategy)
        → parse alert_conditions (JSON)
        → get latest FundDailyPrice for fund_id
        → _evaluate_conditions(conditions, price) → bool
        → if triggered: create AlertLog + send_feishu_card_message()
```

**Key Models:**
- `Strategy`: name, fund_id(FK), type("dca"), config(JSON), alert_enabled, alert_conditions(JSON), is_active
- `AlertLog`: strategy_id, fund_id, triggered_at(ISO string), condition_desc(JSON), current_values(JSON), notified(bool)
- `BacktestResult`: strategy_id, fund_id, dates, metrics (return, sharpe, drawdown, etc.), trade_log(JSON), equity_curve(JSON)

**Alert Condition Format:**
```json
[{"field": "dev_60", "operator": "<", "threshold": -5}]
// or
{"logic": "and|or", "items": [...]}
```
- Fields: dev_30/60/90/120/180/360 from FundDailyPrice
- Operators: <, >, <=, >=, ==

### 2.3 Assistant (Claude AI Integration)

```
POST /api/v1/assistant/chat
  → api/assistant.py::chat(req)
    → rate limit check (10/min, in-memory)
    → get_config("anthropic_api_key")
    → anthropic.Anthropic(api_key=...)
    → client.messages.create(model="claude-sonnet-4-20250514", tools=TOOL_DEFINITIONS)
    → tool_use loop (max 3 rounds)
      → execute_tool(name, args) → JSON string
    → return {reply, tool_calls}
```

**Tool System:**
- 10 tools defined in `services/assistant/tools.py`
- Tools are internal DB queries (no HTTP), read-only except `update_config` (safe keys only)
- Tools: get_funds, get_fund_prices, get_deviation_summary, get_portfolio_latest, get_portfolio_snapshots, get_exchange_rates, get_strategies, get_recent_alerts, get_configs, update_config
- Each tool creates its own DB session via `SessionLocal()`
- SYSTEM_PROMPT defines the assistant as "萌可" (fund management AI assistant)

### 2.4 Guru Module

```
GET /api/v1/guru/gurus → list all gurus by category
GET /api/v1/guru/gurus/{slug}/holdings → guru's stock holdings
GET /api/v1/guru/stocks → search stocks held by gurus
POST /api/v1/guru/refresh → update_all_guru_holdings()
```

**Key Models:**
- `Guru`: name, slug, category(china_fund/asia/north_america), holdings/trades relationships
- `GuruHolding`: guru_id, stock_code, stock_name, weight_pct, sector, return metrics
- `GuruTrade`: guru_id, stock_code, action, shares_changed, trade_date
- `GuruStock`: code(unique), name, market(A/HK/US/TW), sector, guru_count

**Note:** All string fields for numeric values (shares, value, weight_pct) -- no float columns

### 2.5 Notification (Feishu)

```
send_feishu_card_message(title, content, chat_id?)
  → get_config(feishu_app_id, feishu_app_secret, feishu_webhook_url)
  → _get_tenant_access_token() if needed
  → _send_via_webhook() if webhook_url configured (preferred)
  → or send via Feishu Open API (im/v1/messages) with chat_id
```

- Card format: header(title, blue template) + elements(markdown content)
- Uses httpx for HTTP calls, timeout=10s
- Returns bool (success/failure)

### 2.6 Scheduler

- `APScheduler BackgroundScheduler` started in app lifespan
- Job execution pattern: `@_record_run("job_id")` decorator → creates `JobRun` record
- Each job creates its own `SessionLocal()` DB session
- Jobs: market_data(hourly), strategy_check(9/12/14), webank_import(daily 9:00), weekly_data_completion(Mon 8:00), fund_holdings(monthly 1st), market_insight(Mon 8:30), auto_backup(daily 2:00), guru_update(monthly 5th), alipay_import(daily 9:05)

### 2.7 Diary Module (Related)

- `DiaryEntry`: entry_date, title, content, mood(bullish/neutral/bearish), tags(JSON), timestamps
- Already provides journaling capability, could integrate with "Letter to Future Self" (FR-CONST-017)

---

## 3. Existing Patterns to Follow

### Backend Patterns

| Pattern | Convention | Example |
|---------|-----------|---------|
| **Model** | SQLAlchemy declarative, `app.database.Base` | `models/portfolio.py` |
| **API Router** | `APIRouter()`, prefix in `main.py` | `/api/v1/portfolio` |
| **DB Session** | `Depends(get_db)` in endpoints, `SessionLocal()` in services/jobs | `api/portfolio.py` |
| **Response** | `ok(data, meta?)` / `fail(error)` → `{success, data, error, meta}` | `response.py` |
| **Schema** | Pydantic `BaseModel`, `model_config = {"from_attributes": True}` | `schemas/portfolio.py` |
| **JSON storage** | Text columns with JSON strings for flexible data | `Strategy.config`, `AlertLog.current_values` |
| **DB** | SQLite with WAL mode, foreign_keys=ON | `database.py` |
| **Tables** | Auto-created via `Base.metadata.create_all(bind=engine)` at startup | `main.py` lifespan |
| **No migrations** | Alembic NOT used; tables created on startup | - |
| **Config** | `SystemConfig` table, `get_config(key, default)` | `services/config_service.py` |
| **Error handling** | `HTTPException` for API errors | All API files |

### Frontend Patterns

| Pattern | Convention | Example |
|---------|-----------|---------|
| **API calls** | `get<T>(url, params)`, `post<T>(url, data)` via axios | `services/api.ts` |
| **Response type** | `ApiResponse<T> = {success, data, error, meta}` | `types/index.ts` |
| **Routing** | React Router v6, nested under `<AppLayout>` | `App.tsx` |
| **UI framework** | Ant Design (antd) + custom CSS | Portfolio page |
| **State** | React hooks (useState, useCallback, useMemo, useEffect) | `pages/Portfolio/index.tsx` |
| **Locale** | Chinese (zhCN) by default | `App.tsx` |
| **Copilot** | `<CopilotSection>` wraps sections for AI context | Portfolio page |

---

## 4. Data Model Status

### Exists (Reusable)

| Model | Relevance to Discipline System |
|-------|-------------------------------|
| `Fund` | Core entity; buy/sell targets link here |
| `FundDailyPrice` | MA deviations used for alert conditions; PE data NOT here yet |
| `PortfolioRecord` | Current holdings (weekly); need real-time position for constraint checks |
| `PortfolioSnapshot` | Historical total assets; useful for drawdown calculations |
| `Strategy` + `AlertLog` | Existing alert framework; new alerts build on same pattern |
| `Guru` / `GuruHolding` / `GuruTrade` | Guru signals for buy/sell alerts |
| `RebalanceTarget` | Target allocation percentages; useful for plan deviation checks |
| `DiaryEntry` | Journaling; "Letter to Future Self" can extend this |
| `SystemConfig` | Config storage for new feature settings |
| `JobRun` | Scheduler job tracking |

### Needs to Be Added

| New Model | Purpose | Key Fields |
|-----------|---------|------------|
| `InvestmentPlan` | User's investment plan | principal, annual_target, risk_level, investment_period, asset_allocation(JSON), buy_conditions(JSON), sell_conditions(JSON), position_rules(JSON), status(draft/active/locked), locked_at, cooldown_until, panic_letter |
| `PlanRevisionLog` | Plan modification history | plan_id, changed_fields(JSON), old_values(JSON), new_values(JSON), changed_at |
| `DisciplineAlert` | New multi-type alert system | type(buy_opportunity/sell_signal/rebalance/risk_warning/weekly_review), severity(green/orange/blue/red), title, content(JSON), trigger_conditions(JSON), status(unread/read/acted/dismissed), fund_id?, created_at |
| `TradeIntent` | Trade evaluation record | fund_id, direction(buy/sell), amount, status(evaluating/approved/rejected/cooled/executed/cancelled), ai_score, score_breakdown(JSON), conversation_id |
| `TradeConversation` | AI evaluation dialog | intent_id, messages(JSON), evaluation_result(JSON), created_at |
| `CoolingPeriod` | Cooling-off tracking | intent_id?, plan_id?, reason, starts_at, ends_at, original_action(JSON), final_decision(proceed/adjust/cancel), decided_at |
| `MonthlyTradeStats` | Monthly trade budget tracking | year_month, trade_count, trade_limit, excess_count |
| `DisciplineReport` | Weekly/monthly/quarterly reports | type(weekly/monthly/quarterly), period_start, period_end, content(JSON), generated_at |

---

## 5. Reuse Opportunities

### Direct Reuse

1. **Feishu Notification** (`services/notification/feishu.py`): Already supports card messages with markdown. All new alert types (buy/sell/rebalance/risk) can use `send_feishu_card_message()` directly. Just vary title/content/template color.

2. **Claude API Integration** (`api/assistant.py` + `services/assistant/`): The existing chat endpoint and tool system can be extended for TradeEval dialog. Add new tools (e.g., `evaluate_trade_intent`, `get_plan_status`, `check_cooling_period`). The multi-round tool-use loop (max 3 rounds) may need to increase to 5 for evaluation dialogs.

3. **Strategy Evaluator Pattern** (`services/strategy/evaluator.py`): The `_evaluate_conditions()` engine supports field/operator/threshold with AND/OR logic. New alert conditions can follow the same schema. Consider extracting it as a shared utility.

4. **Scheduler Framework** (`scheduler/`): The `@_record_run` decorator + `start_scheduler()` pattern. New jobs (weekly report generation, cooling period expiry check, daily discipline check) fit naturally.

5. **Portfolio Data** (`models/portfolio.py`, `api/portfolio.py`): Breakdown, trend, and snapshot APIs provide the data needed for plan deviation checks and report generation.

6. **Guru Data** (`models/guru.py`): GuruHolding and GuruTrade data can feed buy/sell alert conditions (guru_count, recent trades).

7. **Rebalance Targets** (`models/rebalance.py`): Already stores target allocation percentages per classification model/category. Can be linked to investment plan's target allocation.

8. **DiaryEntry** (`models/diary.py`): The "Letter to Future Self" (FR-CONST-017/018/019) can be stored as a special DiaryEntry with a tag or a new field on InvestmentPlan.

### Extend/Adapt

1. **`FundDailyPrice`**: Needs PE, PB, ROE fields OR a new `FundValuation` model to support valuation-based alert conditions (FR-EVAL-003, FR-ALERT-007).

2. **`Strategy.alert_conditions`**: Current alert system is fund-level (one fund per strategy). New alerts need portfolio-level checks (drawdown, allocation deviation). Consider new models rather than overloading Strategy.

3. **Assistant tools**: Add 5-8 new tools for the discipline system (get_plan, get_trade_intents, check_constraints, etc.).

---

## 6. Risk Markers

### R1: No Transaction Model (HIGH)
The system currently tracks **weekly asset snapshots**, not individual trades. The Investment Discipline system is fundamentally trade-centric (evaluate trade intent, count monthly trades, track cooling periods). A `TradeIntent` model is the critical gap. Existing `PortfolioRecord` is NOT a trade log.

### R2: No Valuation Data (MEDIUM)
`FundDailyPrice` has MA deviations but NO PE/PB/ROE/GF Value data. PRD requires PE-based conditions (FR-ALERT-007, FR-EVAL-003). Options:
- Add columns to `FundDailyPrice`
- Create a new `FundValuation` model
- Fetch from GuruFocus API at evaluation time (latency risk)

### R3: Single-User Assumption (LOW)
No authentication or user model exists. The entire system is single-user. Investment plans, cooling periods, and trade intents are all single-user. This is fine for current scope but limits future expansion.

### R4: SQLite Limitations (LOW)
SQLite with WAL mode works for single-user. But concurrent scheduler jobs + API requests writing to new tables (TradeIntent, CoolingPeriod) could hit write contention. Monitor; likely acceptable for single-user scale.

### R5: Claude API Cost (MEDIUM)
Current assistant uses `claude-sonnet-4-20250514` with max_tokens=2048. Trade evaluation dialogs (3-5 rounds per trade) will significantly increase API usage. Consider:
- Token budget per evaluation session
- Caching common evaluation patterns
- Using structured output to reduce token waste

### R6: Alert System Overlap (MEDIUM)
Existing `Strategy` + `AlertLog` handles fund-level deviation alerts. New `DisciplineAlert` handles portfolio-level and multi-condition alerts. Need clear separation:
- Keep existing Strategy/AlertLog for simple MA-based fund alerts
- New DisciplineAlert for investment plan-related alerts (types A-E in PRD)
- Consider eventually migrating old alerts to new system (P2)

### R7: No Alembic Migrations (LOW-MEDIUM)
Tables are auto-created at startup via `create_all()`. Adding 8+ new models is fine for initial creation, but future schema changes (add/rename columns) will require manual ALTER TABLE or adopting Alembic. Recommend adding Alembic before this feature if practical.

### R8: JSON Text Columns (LOW)
Many models use `Text` columns for JSON data (Strategy.config, AlertLog.current_values). This pattern works but prevents SQL-level filtering on JSON fields. New models should use JSON columns where filtering is needed (SQLite supports `json_extract()` since 3.9).

---

## 7. Architecture Recommendation Summary

```
New Backend Structure:
  backend/app/
    models/
      discipline/
        plan.py          # InvestmentPlan, PlanRevisionLog
        alert.py         # DisciplineAlert
        trade.py         # TradeIntent, TradeConversation
        constraint.py    # CoolingPeriod, MonthlyTradeStats
        report.py        # DisciplineReport
    schemas/
      discipline/
        plan.py
        alert.py
        trade.py
        constraint.py
        report.py
    api/
      discipline/
        plan.py
        alert.py
        trade.py
        constraint.py
        report.py
    services/
      discipline/
        plan_service.py
        alert_engine.py       # extends evaluator pattern
        trade_evaluator.py    # Claude-based evaluation
        constraint_checker.py
        report_generator.py

New Frontend Structure:
  frontend/src/
    pages/
      Discipline/
        PlanWizard.tsx      # 5-step plan creation
        PlanDashboard.tsx   # plan status overview
        AlertCenter.tsx     # alert list + detail
        TradeEval.tsx       # chat-based evaluation
        Reports.tsx         # report list + detail
    services/
      api.ts                # extend with discipline API calls
    types/
      index.ts              # extend with discipline types

New Scheduler Jobs:
  - discipline_alert_check: hourly, runs alert engine
  - cooling_period_expiry: every 30min, checks expiring cooling periods
  - weekly_report: Friday 16:00, generates weekly report
  - monthly_report: 1st of month 8:00, generates monthly report

New Configs (SystemConfig):
  - discipline_enabled: "true"
  - trade_eval_model: "claude-sonnet-4-20250514"
  - trade_eval_max_rounds: "5"
  - cooling_period_plan_hours: "48"
  - cooling_period_trade_hours: "24"
  - monthly_trade_limit: "8"
```