# Infrastructure & Configuration

## Docker Compose

File: `docker-compose.yml` (version 3.8)

### Services

| Service | Image | Port | Volumes | Restart |
|---------|-------|------|---------|---------|
| backend | `./backend` (python:3.11-slim) | 8000:8000 | `sqlite_data:/app/data` | unless-stopped |
| frontend | `./frontend` (node:20-alpine build + nginx:alpine) | 3000:80 | none | unless-stopped |

### Named Volumes

- `sqlite_data` - persists SQLite database file at `/app/data/fundasset.db`

### Backend Dockerfile

```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

Multi-stage build:
1. Stage 1: `node:20-alpine` - `npm ci` + `npm run build`
2. Stage 2: `nginx:alpine` - copy `dist/` to `/usr/share/nginx/html`

### Nginx Configuration

File: `frontend/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    
    location /api/ {
        proxy_pass http://backend:8000;
    }
    
    location / {
        try_files $uri $uri/ /index.html;  # SPA fallback
    }
}
```

## Environment Configuration

### Backend `.env.example`

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLite connection string (default: `sqlite:///./data/fundasset.db`) |
| `TUSHARE_TOKEN` | Tushare API token |
| `FEISHU_APP_ID` | Feishu app credentials |
| `FEISHU_APP_SECRET` | Feishu app credentials |
| `FEISHU_WEBHOOK_URL` | Feishu notification webhook |

### Frontend `.env`

| Variable | Purpose |
|----------|---------|
| `VITE_API_URL` | Backend API base URL (default: `http://localhost:8000`) |
| `VITE_CCREMOTE_URL` | CCRemote AI assistant service URL |

### Backend Settings (Pydantic)

```python
class Settings(BaseSettings):
    app_name: str = "BeFriend FundAsset"
    database_url: str = "sqlite:///./data/fundasset.db"
    
    class Config:
        env_file = ".env"
```

## Runtime Configuration (system_config table)

All runtime settings are stored in the `system_config` DB table and managed via `config_service.py`. Env vars are migrated to DB on first startup.

### Config Categories

| Category | Keys |
|----------|------|
| `api` | `tushare_token`, `feishu_app_id`, `feishu_app_secret`, `feishu_webhook_url`, `anthropic_api_key` |
| `scheduler` | `scheduler_market_cron`, `scheduler_strategy_hours` |
| `exchange` | `exchange_rate_pairs`, `backfill_years`, `default_rate_usd_cny`, `default_rate_hkd_cny` |
| `email` | `imap_email`, `imap_password`, `imap_host`, `webank_zip_password`, `webank_auto_import_enabled`, `webank_auto_import_cron`, `alipay_auto_import_enabled` |
| `backup` | `backup_enabled`, `backup_retention_count` |

## Scheduler Configuration

APScheduler `BackgroundScheduler` runs in-process with the FastAPI application.

### Schedule Summary

| Job | Cron | Configurable |
|-----|------|-------------|
| Market data fetch | Every hour at :00 | No |
| Strategy check | Configurable hours (default 9,12,14) | Yes, via `scheduler_strategy_hours` |
| WeBank import | Daily 09:00 | Toggle via `webank_auto_import_enabled` |
| Alipay import | Daily 09:05 | Toggle via `alipay_auto_import_enabled` |
| Weekly data completion | Monday 08:00 | No |
| Fund holdings fetch | 1st of month 10:00 | No |
| Market insight refresh | Monday 08:30 | No |
| Auto backup | Daily 02:00 | No |
| Guru holdings update | 5th of month 10:30 | No |

## Startup Sequence

1. Create `data/` directory
2. `Base.metadata.create_all()` - auto-create all tables
3. Start APScheduler
4. Background thread: `_init_and_backfill()`
   - Insert default configs (migrate env vars)
   - Backfill exchange rates if < 200 records per pair

## Dependencies

### Backend (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115.0 | Web framework |
| uvicorn[standard] | 0.30.0 | ASGI server |
| sqlalchemy | 2.0.35 | ORM |
| alembic | 1.13.2 | Migration tool (installed but not used) |
| pydantic | 2.9.0 | Data validation |
| pydantic-settings | 2.5.0 | Settings management |
| pandas | 2.2.2 | Data analysis |
| numpy | 1.26.4 | Numerical computing |
| tushare | 1.4.2 | Chinese market data API |
| yfinance | 0.2.40 | Yahoo Finance API |
| akshare | >=1.12.0 | Alternative market data API |
| apscheduler | 3.10.4 | Task scheduler |
| httpx | 0.27.0 | HTTP client (Feishu, etc.) |
| anthropic | >=0.40.0 | Claude AI SDK |
| pdfplumber | >=0.10.0 | PDF parsing (WeBank statements) |
| openpyxl | >=3.1.0 | Excel file handling |
| python-multipart | >=0.0.9 | File upload support |

### Frontend (package.json)

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^19.2.4 | UI framework |
| antd | ^6.3.6 | UI component library |
| echarts | ^6.0.0 | Charts |
| echarts-for-react | ^3.0.6 | React ECharts wrapper |
| axios | ^1.15.0 | HTTP client |
| react-router-dom | ^7.14.1 | Client-side routing |
| typescript | ~6.0.2 | Type system |
| vite | ^8.0.4 | Build tool |
| @playwright/test | ^1.59.1 | E2E testing |
