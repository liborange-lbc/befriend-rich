import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.price import ExchangeRate
from app.services.config_service import get_config
from app.services.market_data.yahoo_adapter import YahooAdapter

logger = logging.getLogger(__name__)


def get_all_pairs() -> list[str]:
    pairs_str = get_config("exchange_rate_pairs", "USD/CNY,HKD/CNY")
    return [p.strip() for p in pairs_str.split(",") if p.strip()]


def fetch_and_store_exchange_rate(
    db: Session, target_date: date | None = None, pair: str = "USD/CNY"
):
    if target_date is None:
        target_date = date.today()

    adapter = YahooAdapter()
    df = adapter.fetch_exchange_rate(pair, target_date, target_date)

    if df.empty:
        logger.warning(f"No exchange rate data for {pair} on {target_date}, trying previous days")
        for i in range(1, 8):
            prev = target_date - timedelta(days=i)
            df = adapter.fetch_exchange_rate(pair, prev, prev)
            if not df.empty:
                break

    if df.empty:
        logger.error(f"Failed to fetch exchange rate for {pair}")
        return None

    for _, row in df.iterrows():
        existing = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.date == row["date"], ExchangeRate.pair == pair)
            .first()
        )
        if existing:
            existing.rate = float(row["rate"])
        else:
            db.add(ExchangeRate(date=row["date"], pair=pair, rate=float(row["rate"])))

    db.commit()
    return df.iloc[-1]["rate"] if not df.empty else None


def fetch_and_store_all_rates(db: Session, target_date: date | None = None):
    for pair in get_all_pairs():
        try:
            fetch_and_store_exchange_rate(db, target_date, pair)
        except Exception as e:
            logger.error(f"Failed to fetch {pair}: {e}")


def backfill_exchange_rate(db: Session, pair: str, start_date: date, end_date: date):
    adapter = YahooAdapter()
    df = adapter.fetch_exchange_rate(pair, start_date, end_date)

    if df.empty:
        logger.warning(f"No exchange rate data for {pair} from {start_date} to {end_date}")
        return 0

    count = 0
    for _, row in df.iterrows():
        existing = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.date == row["date"], ExchangeRate.pair == pair)
            .first()
        )
        if existing:
            existing.rate = float(row["rate"])
        else:
            db.add(ExchangeRate(date=row["date"], pair=pair, rate=float(row["rate"])))
            count += 1

    db.commit()
    logger.info(f"Backfilled {count} exchange rate records for {pair}")
    return count


def get_latest_rate(db: Session, pair: str = "USD/CNY") -> float:
    rate = (
        db.query(ExchangeRate)
        .filter(ExchangeRate.pair == pair)
        .order_by(ExchangeRate.date.desc())
        .first()
    )
    if rate:
        return rate.rate
    defaults = {
        "USD/CNY": float(get_config("default_rate_usd_cny", "7.25")),
        "HKD/CNY": float(get_config("default_rate_hkd_cny", "0.93")),
    }
    return defaults.get(pair, 1.0)
