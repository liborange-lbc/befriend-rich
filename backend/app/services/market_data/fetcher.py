import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.services.analysis.moving_average import calculate_and_store_indicators
from app.services.market_data.akshare_adapter import AkshareAdapter
from app.services.market_data.base import DataSourceAdapter
from app.services.market_data.tushare_adapter import TushareAdapter
from app.services.market_data.yahoo_adapter import YahooAdapter

logger = logging.getLogger(__name__)

ADAPTERS: dict[str, type[DataSourceAdapter]] = {
    "tushare": TushareAdapter,
    "yahoo": YahooAdapter,
    "akshare": AkshareAdapter,
}


def fetch_prices_for_fund(
    db: Session, fund: Fund, start_date: date, end_date: date
):
    adapter_cls = ADAPTERS.get(fund.data_source)
    if not adapter_cls:
        logger.error(f"Unknown data source: {fund.data_source}")
        return

    adapter = adapter_cls()
    df = adapter.fetch_daily_prices(fund.code, start_date, end_date)

    if df.empty:
        logger.warning(f"No price data for {fund.code}")
        return

    for _, row in df.iterrows():
        existing = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund.id, FundDailyPrice.date == row["date"])
            .first()
        )
        if existing:
            existing.close_price = float(row["close"])
        else:
            db.add(
                FundDailyPrice(
                    fund_id=fund.id,
                    date=row["date"],
                    close_price=float(row["close"]),
                )
            )
    db.commit()
    calculate_and_store_indicators(db, fund.id)


def fetch_all_active_funds(db: Session, target_date: date | None = None):
    if target_date is None:
        target_date = date.today()

    funds = db.query(Fund).filter(Fund.is_active == True).all()
    for fund in funds:
        try:
            fetch_prices_for_fund(db, fund, target_date, target_date)
        except Exception as e:
            logger.error(f"Failed to fetch {fund.code}: {e}")
            continue
