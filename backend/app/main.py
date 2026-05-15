import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date

# 全局时区设置为东八区
os.environ["TZ"] = "Asia/Shanghai"
if hasattr(time, "tzset"):
    time.tzset()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    allocation,
    analysis,
    assistant,
    backup,
    backtest,
    baduanjin,
    exercise,
    xunji,
    classification,
    config,
    correlation,
    dashboard,
    data_health,
    db_viewer,
    export,
    family,
    fund_compare,
    fund_holding,
    funds,
    guru,
    ic_option,
    import_data,
    market_data,
    market_insight,
    nanny_salary,
    portfolio,
    us_stock_trend,
    watch,
    wechat_auth,
    wechat_steps,
    return_attribution,
    scheduler,
    strategy,
    valuation,
)
from app.database import Base, SessionLocal, engine
from app.models.config import SystemConfig  # noqa: F401 — ensure table created
from app.models.scheduler import JobRun  # noqa: F401 — ensure table created
from app.models.fund_holding import FundHolding  # noqa: F401 — ensure table created
from app.models.import_log import ImportLog  # noqa: F401 — ensure table created
from app.models.market_insight import MarketIndexComponent, MarketStock  # noqa: F401
from app.models.us_stock_trend import USStockVolumeRanking  # noqa: F401
from app.models.rebalance import RebalanceTarget  # noqa: F401 — ensure table created
from app.models.allocation import AllocationSnapshot, AllocationTarget  # noqa: F401
from app.models.guru import Guru, GuruHolding, GuruStock, GuruTrade  # noqa: F401
from app.models.ic_option import ICOptionPrice  # noqa: F401
from app.models.nanny_salary import NannySalaryConfig, NannySalaryHoliday, NannySalaryLeave  # noqa: F401
from app.models.family import FamilyProfile, InjuryRecord  # noqa: F401
from app.models.watch import GarminDailySummary, WatchActivity, WatchConnection  # noqa: F401
from app.models.wechat_steps import WechatStep  # noqa: F401
from app.models.wechat_user import WechatUser  # noqa: F401 — ensure table created
from app.models.baduanjin import BaduanjinRecord  # noqa: F401 — ensure table created
from app.models.xunji import XunjiTrainCache  # noqa: F401 — ensure table created
from app.models.exercise import ExerciseRecord  # noqa: F401 — unified exercise table
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


def _run_migrations():
    """Lightweight ALTER TABLE migrations for SQLite (no alembic)."""
    from sqlalchemy import inspect, text
    with engine.connect() as conn:
        inspector = inspect(engine)
        # Add openid column to wechat_family_profiles if missing
        cols = [c["name"] for c in inspector.get_columns("wechat_family_profiles")]
        if "openid" not in cols:
            conn.execute(text("ALTER TABLE wechat_family_profiles ADD COLUMN openid VARCHAR(64)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wechat_family_profiles_openid ON wechat_family_profiles(openid)"))
            conn.commit()
            logger.info("Migration: added openid column to wechat_family_profiles")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _run_migrations()
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
app.include_router(backup.router, prefix="/api/v1/backup", tags=["backup"])
app.include_router(data_health.router, prefix="/api/v1/data-health", tags=["data-health"])
app.include_router(fund_compare.router, prefix="/api/v1/fund-compare", tags=["fund-compare"])
app.include_router(correlation.router, prefix="/api/v1/correlation", tags=["correlation"])
app.include_router(return_attribution.router, prefix="/api/v1/attribution", tags=["attribution"])
app.include_router(valuation.router, prefix="/api/v1/valuation", tags=["valuation"])
app.include_router(export.router, prefix="/api/v1/export", tags=["export"])
app.include_router(guru.router, prefix="/api/v1/guru", tags=["guru"])
app.include_router(allocation.router, prefix="/api/v1/allocation", tags=["allocation"])
app.include_router(ic_option.router, prefix="/api/v1/ic-option", tags=["ic-option"])
app.include_router(nanny_salary.router, prefix="/api/v1/nanny-salary", tags=["nanny-salary"])
app.include_router(wechat_auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(wechat_steps.router, prefix="/api/v1/wechat-steps", tags=["wechat-steps"])
app.include_router(family.router, prefix="/api/v1/family", tags=["family"])
app.include_router(watch.router, prefix="/api/v1/watch", tags=["watch"])
app.include_router(baduanjin.router, prefix="/api/v1/baduanjin", tags=["baduanjin"])
app.include_router(xunji.router, prefix="/api/v1/xunji", tags=["xunji"])
app.include_router(exercise.router, prefix="/api/v1/exercise", tags=["exercise"])
app.include_router(us_stock_trend.router, prefix="/api/v1/us-stock-trend", tags=["us-stock-trend"])
app.include_router(db_viewer.router, prefix="/api/v1/db-viewer", tags=["db-viewer"])


os.makedirs("data/avatars", exist_ok=True)
os.makedirs("data/media", exist_ok=True)
os.makedirs("data/static", exist_ok=True)
app.mount("/static/media", StaticFiles(directory="data/media"), name="media")
app.mount("/static/pages", StaticFiles(directory="data/static"), name="static-pages")
app.mount("/static/avatars", StaticFiles(directory="data/avatars"), name="avatars")


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}
