import os

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.config import SystemConfig

# Default config definitions: (key, default_value, category, description)
DEFAULTS = [
    ("tushare_token", "", "api", "Tushare API Token"),
    ("feishu_app_id", "", "api", "飞书应用 App ID"),
    ("feishu_app_secret", "", "api", "飞书应用 App Secret"),
    ("feishu_webhook_url", "", "api", "飞书 Webhook URL"),
    ("scheduler_market_cron", "0 * * * *", "scheduler", "行情数据抓取 Cron (每小时)"),
    ("scheduler_strategy_hours", "9,12,14", "scheduler", "策略检查时间 (小时, 逗号分隔)"),
    ("exchange_rate_pairs", "USD/CNY,HKD/CNY", "exchange", "汇率币种对 (逗号分隔)"),
    ("backfill_years", "10", "exchange", "历史数据回填年限"),
    ("default_rate_usd_cny", "7.25", "exchange", "USD/CNY 默认汇率"),
    ("default_rate_hkd_cny", "0.93", "exchange", "HKD/CNY 默认汇率"),
]


def init_default_configs(db: Session) -> None:
    """Insert default configs if they don't exist. Migrate env vars on first run."""
    for key, default, category, description in DEFAULTS:
        existing = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if not existing:
            env_val = os.environ.get(key.upper(), "")
            value = env_val if env_val else default
            db.add(SystemConfig(key=key, value=value, category=category, description=description))
        elif not existing.value and existing.value != default:
            # If DB has empty value but env has one, migrate it
            env_val = os.environ.get(key.upper(), "")
            if env_val:
                existing.value = env_val
    db.commit()


def get_config(key: str, default: str = "") -> str:
    """Read a config value. Priority: database > default."""
    db = SessionLocal()
    try:
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        return row.value if row and row.value else default
    finally:
        db.close()


def get_config_with_db(db: Session, key: str, default: str = "") -> str:
    """Read a config value using an existing session."""
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return row.value if row and row.value else default
