import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analysis,
    assistant,
    backtest,
    classification,
    config,
    dashboard,
    fund_holding,
    funds,
    import_data,
    market_data,
    market_insight,
    portfolio,
    scheduler,
    strategy,
)
from app.database import Base, SessionLocal, engine
from app.models.config import SystemConfig  # noqa: F401 — ensure table created
from app.models.scheduler import JobRun  # noqa: F401 — ensure table created
from app.models.fund_holding import FundHolding  # noqa: F401 — ensure table created
from app.models.import_log import ImportLog  # noqa: F401 — ensure table created
from app.models.market_insight import MarketIndexComponent, MarketStock  # noqa: F401
from app.models.price import ExchangeRate
from app.scheduler.setup import start_scheduler, stop_scheduler
from app.services.config_service import get_config, init_default_configs
from app.services.market_data.exchange_rate import backfill_exchange_rate

logger = logging.getLogger(__name__)


def _init_and_backfill():
    db = SessionLocal()
    try:
        init_default_configs(db)

        # Read config from DB
        pairs_str = get_config("exchange_rate_pairs", "USD/CNY,HKD/CNY")
        pairs = [p.strip() for p in pairs_str.split(",") if p.strip()]
        years = int(get_config("backfill_years", "10"))

        today = date.today()
        start = date(today.year - years, today.month, today.day)

        for pair in pairs:
            count = db.query(ExchangeRate).filter(ExchangeRate.pair == pair).count()
            if count < 200:
                logger.info(f"Backfilling {pair} exchange rate (current: {count} records)")
                backfill_exchange_rate(db, pair, start, today)
    except Exception as e:
        logger.error(f"Init/backfill failed: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    threading.Thread(target=_init_and_backfill, daemon=True).start()
    yield
    stop_scheduler()


app = FastAPI(title="BeFriend FundAsset", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(funds.router, prefix="/api/v1/funds", tags=["funds"])
app.include_router(classification.router, prefix="/api/v1/classification", tags=["classification"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
app.include_router(market_data.router, prefix="/api/v1/market-data", tags=["market-data"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
app.include_router(strategy.router, prefix="/api/v1/strategy", tags=["strategy"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
app.include_router(import_data.router, prefix="/api/v1/import", tags=["import"])
app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["assistant"])
app.include_router(market_insight.router, prefix="/api/v1/market-insight", tags=["market-insight"])
app.include_router(fund_holding.router, prefix="/api/v1/fund-xray", tags=["fund-xray"])
app.include_router(scheduler.router, prefix="/api/v1/scheduler", tags=["scheduler"])


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}
