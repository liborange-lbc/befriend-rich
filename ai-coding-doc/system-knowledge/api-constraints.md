# API Constraints

## URL Naming

- All routes under `/api/v1/` prefix
- Kebab-case for multi-word resources: `market-data`, `fund-xray`, `data-health`, `fund-compare`, `market-insight`
- No trailing slashes

### Registered Route Prefixes (25)

| Prefix | Tag | Router File |
|--------|-----|-------------|
| `/api/v1/funds` | funds | `api/funds.py` |
| `/api/v1/classification` | classification | `api/classification.py` |
| `/api/v1/portfolio` | portfolio | `api/portfolio.py` |
| `/api/v1/market-data` | market-data | `api/market_data.py` |
| `/api/v1/analysis` | analysis | `api/analysis.py` |
| `/api/v1/backtest` | backtest | `api/backtest.py` |
| `/api/v1/strategy` | strategy | `api/strategy.py` |
| `/api/v1/dashboard` | dashboard | `api/dashboard.py` |
| `/api/v1/config` | config | `api/config.py` |
| `/api/v1/import` | import | `api/import_data.py` |
| `/api/v1/assistant` | assistant | `api/assistant.py` |
| `/api/v1/market-insight` | market-insight | `api/market_insight.py` |
| `/api/v1/fund-xray` | fund-xray | `api/fund_holding.py` |
| `/api/v1/scheduler` | scheduler | `api/scheduler.py` |
| `/api/v1/backup` | backup | `api/backup.py` |
| `/api/v1/data-health` | data-health | `api/data_health.py` |
| `/api/v1/fund-compare` | fund-compare | `api/fund_compare.py` |
| `/api/v1/correlation` | correlation | `api/correlation.py` |
| `/api/v1/attribution` | attribution | `api/return_attribution.py` |
| `/api/v1/valuation` | valuation | `api/valuation.py` |
| `/api/v1/rebalance` | rebalance | `api/rebalance.py` |
| `/api/v1/diary` | diary | `api/diary.py` |
| `/api/v1/export` | export | `api/export.py` |
| `/api/v1/guru` | guru | `api/guru.py` |
| `/api/v1/health` | (inline) | `main.py` |

## Versioning

Single version `v1` in URL path. No header-based versioning.

## Response Format

Unified envelope via `app/response.py`:

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None
```

### Helper Functions

```python
ok(data, meta=None)   -> {"success": True, "data": ..., "error": None, "meta": ...}
fail(error, status_code=400) -> {"success": False, "data": None, "error": "..."}
```

### Usage Pattern

All endpoints return `ok(...)` for success. The `fail()` helper exists but is rarely used -- most error paths raise `HTTPException` instead.

## Error Handling

- **400**: Validation errors (duplicate codes, invalid input) via `HTTPException`
- **404**: Resource not found via `HTTPException`
- **429**: Rate limiting (assistant endpoint, in-memory counter)
- **500**: Unexpected errors via `HTTPException`
- **503**: Missing configuration (e.g., Anthropic API key not set)

Error messages are in Chinese for user-facing errors.

## Pagination

Used in list endpoints (e.g., `/api/v1/funds`):

```
Query params: page (default 1), page_size (default 20, max 100)
Response meta: {"total": N, "page": P, "page_size": S}
```

## Request/Response DTOs

- Pydantic v2 models in `app/schemas/`
- `model_config = {"from_attributes": True}` for ORM compatibility
- `FundCreate` / `FundUpdate` / `FundResponse` naming pattern
- Update DTOs use `Optional` fields with `exclude_unset=True` for partial updates

## Authentication

None. Single-user local deployment. CORS allows all origins.

## Health Check

`GET /api/v1/health` returns `{"status": "ok"}` (not wrapped in ApiResponse envelope).
