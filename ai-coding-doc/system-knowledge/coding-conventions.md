# Coding Conventions

## Backend (Python)

### Project Structure

```
backend/
  app/
    api/          # FastAPI routers (one file per domain)
    models/       # SQLAlchemy models (one file per domain)
    schemas/      # Pydantic v2 DTOs
    services/     # Business logic, organized by domain sub-packages
    scheduler/    # APScheduler setup + job definitions
    config.py     # Pydantic Settings
    database.py   # Engine, session, Base
    main.py       # FastAPI app, lifespan, router registration
    response.py   # Unified API response envelope
```

### Naming Conventions

- **Files**: snake_case (`fund_holding.py`, `market_data.py`)
- **Classes**: PascalCase (`FundDailyPrice`, `DataSourceAdapter`)
- **Tables**: snake_case plural (`funds`, `fund_daily_prices`, `portfolio_records`)
- **API routes**: kebab-case (`/market-data`, `/fund-xray`, `/data-health`)
- **Schema naming**: `{Entity}Create`, `{Entity}Update`, `{Entity}Response`

### SQLAlchemy Patterns

- Declarative base via `class Base(DeclarativeBase): pass`
- All models extend `Base` from `app.database`
- Integer auto-increment primary keys
- `Column(...)` style (not mapped_column -- SQLAlchemy 1.x style declarations with 2.0 engine)
- Unique constraints defined in `__table_args__` tuples
- FK on delete: `CASCADE` for owned entities, `SET NULL` for optional references
- No Alembic: tables auto-created via `Base.metadata.create_all()`

### Pydantic Patterns

- v2 style: `model_config = {"from_attributes": True}` for ORM mode
- `model_dump()` and `model_validate()` for serialization
- `exclude_unset=True` for partial update DTOs
- `Field(...)` with validation constraints (`min_length`, `ge`, `le`)

### API Router Patterns

- Each router: `router = APIRouter()` then `@router.get/post/put/delete`
- Dependency injection: `db: Session = Depends(get_db)`
- Return `ok(data)` or `ok(data, meta={...})` for success
- Raise `HTTPException` for errors
- Logging via `logging.getLogger(__name__)`

### Exception Handling

- API layer: `HTTPException` with Chinese detail messages
- Service layer: `try/except` with `logger.error()`, re-raise or return gracefully
- Scheduler jobs: wrapped with `@_record_run()` decorator that catches all exceptions and records status
- No custom exception classes -- stdlib `HTTPException` only

### Logging

- Standard library `logging` module
- One logger per module: `logger = logging.getLogger(__name__)`
- Levels: `info` for normal operations, `warning` for non-critical issues, `error` for failures
- Chinese in some log messages, English in others (mixed)

### Layer Rules

```
API (router) -> Service -> Model/DB
     |              |
     v              v
  Schemas      SQLAlchemy Session
```

- API layer handles HTTP concerns (query params, status codes, response formatting)
- Service layer contains business logic, receives `Session` as parameter
- Models are pure data definitions, no business methods
- Services may import other services directly (no DI container)

### Config Management

- `app/config.py`: Pydantic `BaseSettings` for app-level config (DB URL)
- `system_config` DB table for runtime config (API keys, scheduler settings)
- `get_config(key, default)` function reads from DB
- Environment variables migrated to DB on first startup

## Frontend (TypeScript/React)

### Structure

```
frontend/src/
  pages/          # One directory per page
  components/     # Shared components
    Charts/       # ECharts wrappers
    Assistant/    # AI copilot components
    Layout/       # App shell
  App.tsx         # Router definitions
  main.tsx        # Entry point
```

### Conventions

- Functional components only
- Ant Design 6 for UI primitives
- ECharts via `echarts-for-react` wrapper
- Axios for HTTP calls
- Environment variables via `VITE_*` prefix
