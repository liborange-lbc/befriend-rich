from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.models.price import ExchangeRate, FundDailyPrice
from app.response import ok
from app.services.market_data.exchange_rate import (
    backfill_exchange_rate,
    fetch_and_store_all_rates,
    fetch_and_store_exchange_rate,
)
from app.services.market_data.fetcher import fetch_all_active_funds, fetch_prices_for_fund

router = APIRouter()


@router.post("/fetch")
def trigger_fetch(target_date: date | None = None, db: Session = Depends(get_db)):
    fetch_all_active_funds(db, target_date)
    fetch_and_store_all_rates(db, target_date)
    return ok({"message": "抓取完成"})


@router.post("/backfill/{fund_id}")
def backfill_fund(
    fund_id: int,
    start_date: date = Query(...),
    db: Session = Depends(get_db),
):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        return ok(None, meta={"error": "基金不存在"})
    fetch_prices_for_fund(db, fund, start_date, date.today())
    return ok({"message": f"{fund.code} 历史数据回填完成"})


@router.get("/dates/{fund_id}")
def get_data_dates(
    fund_id: int,
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    dates_query = (
        db.query(FundDailyPrice.date)
        .filter(
            FundDailyPrice.fund_id == fund_id,
            FundDailyPrice.date >= date(year, 1, 1),
            FundDailyPrice.date <= date(year, 12, 31),
        )
        .order_by(FundDailyPrice.date)
        .all()
    )
    dates = [row.date.isoformat() for row in dates_query]

    years_query = (
        db.query(func.distinct(func.strftime("%Y", FundDailyPrice.date)))
        .filter(FundDailyPrice.fund_id == fund_id)
        .all()
    )
    years = sorted([int(row[0]) for row in years_query], reverse=True)

    return ok({"dates": dates, "years": years})


@router.get("/exchange-rate/history")
def get_exchange_rate_history(
    pair: str = Query(default="USD/CNY"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = date(end_date.year - 10, end_date.month, end_date.day)

    records = (
        db.query(ExchangeRate.date, ExchangeRate.rate)
        .filter(
            ExchangeRate.pair == pair,
            ExchangeRate.date >= start_date,
            ExchangeRate.date <= end_date,
        )
        .order_by(ExchangeRate.date)
        .all()
    )
    return ok([{"date": r.date.isoformat(), "rate": round(r.rate, 4)} for r in records])


@router.post("/exchange-rate/backfill")
def trigger_exchange_rate_backfill(
    pair: str = Query(default="USD/CNY"),
    db: Session = Depends(get_db),
):
    today = date.today()
    start = date(today.year - 10, today.month, today.day)
    count = backfill_exchange_rate(db, pair, start, today)
    return ok({"message": f"{pair} 回填完成", "count": count})


@router.post("/exchange-rate/fetch")
def trigger_exchange_rate_fetch(
    target_date: date | None = None, db: Session = Depends(get_db)
):
    rate = fetch_and_store_exchange_rate(db, target_date)
    return ok({"rate": rate})
