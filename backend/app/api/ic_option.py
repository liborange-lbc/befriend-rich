from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.ic_option_service import (
    backfill_history,
    calculate_position,
    calculate_roll_guidance,
    calculate_statistics,
    fetch_and_store,
    get_prices,
)

router = APIRouter()


@router.get("/prices")
def api_get_prices(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    prices = get_prices(db, start_date, end_date)
    stats = calculate_statistics(prices)
    roll = calculate_roll_guidance(prices)
    return ok({"prices": prices, "stats": stats, "roll": roll})


@router.post("/fetch")
def api_fetch_latest(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    counts = fetch_and_store(db, days=days)
    return ok(counts)


@router.post("/backfill")
def api_backfill(
    years: int = Query(default=10, ge=1, le=15),
    db: Session = Depends(get_db),
):
    counts = backfill_history(db, years=years)
    return ok(counts)


@router.get("/position")
def api_position_calc(
    entry_point: float = Query(ge=100),
    entry_capital: float = Query(default=500000, ge=10000),
    margin_rate: float = Query(default=0.12, ge=0.05, le=0.5),
    num_contracts: int | None = Query(default=None, ge=1, le=100),
):
    return ok(calculate_position(entry_point, entry_capital, margin_rate, num_contracts))
