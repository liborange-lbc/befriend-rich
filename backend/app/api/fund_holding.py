"""Fund X-ray API — constituent stock holdings and exposure."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.models.fund_holding import FundHolding
from app.response import ok
from app.services.fund_holding_service import (
    fetch_holdings_for_all_funds,
    fetch_holdings_for_fund,
    get_aggregated_holdings,
    get_available_quarters,
    get_fund_holdings,
    get_fund_positions,
    get_stock_exposure,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/holdings")
def list_holdings(
    fund_id: int | None = Query(default=None),
    quarter: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get holdings for a fund (or all funds)."""
    if fund_id:
        holdings = get_fund_holdings(db, fund_id, quarter)
    else:
        query = db.query(FundHolding)
        if quarter:
            query = query.filter(FundHolding.quarter == quarter)
        holdings = query.order_by(
            FundHolding.fund_id, FundHolding.holding_ratio.desc().nullslast()
        ).all()

    # Attach fund_code / fund_name / holding_amount
    fund_cache: dict[int, Fund] = {}
    positions = get_fund_positions(db)
    result = []
    for h in holdings:
        if h.fund_id not in fund_cache:
            fund_cache[h.fund_id] = db.query(Fund).filter(Fund.id == h.fund_id).first()
        fund = fund_cache[h.fund_id]
        pos = positions.get(h.fund_id, 0.0)
        holding_amount = round(pos * (h.holding_ratio or 0) / 100, 2) if pos and h.holding_ratio else None
        result.append({
            "id": h.id,
            "fund_id": h.fund_id,
            "fund_code": fund.code if fund else None,
            "fund_name": fund.name if fund else None,
            "quarter": h.quarter,
            "stock_code": h.stock_code,
            "stock_name": h.stock_name,
            "holding_ratio": h.holding_ratio,
            "holding_shares": h.holding_shares,
            "holding_value": h.holding_value,
            "holding_amount": holding_amount,
            "disclosure_date": h.disclosure_date,
        })

    fund_position = round(positions.get(fund_id, 0.0), 2) if fund_id else None
    return ok(result, meta={"fund_position": fund_position})


@router.get("/holdings/aggregate")
def aggregate_holdings(
    fund_ids: str = Query(..., description="Comma-separated fund IDs"),
    db: Session = Depends(get_db),
):
    """Get aggregated holdings across multiple funds."""
    ids = [int(x.strip()) for x in fund_ids.split(",") if x.strip().isdigit()]
    if not ids:
        return ok([])
    positions = get_fund_positions(db)
    group_position = round(sum(positions.get(fid, 0.0) for fid in ids), 2)
    result = get_aggregated_holdings(db, ids)
    return ok(result, meta={"fund_position": group_position})


@router.get("/holdings/quarters")
def list_quarters(
    fund_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get distinct quarters available."""
    quarters = get_available_quarters(db, fund_id)
    return ok(quarters)


@router.get("/exposure")
def get_exposure(
    target_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get stock exposure across portfolio."""
    exposure = get_stock_exposure(db, target_date)
    return ok(exposure)


@router.post("/fetch")
def trigger_fetch(
    fund_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Manually trigger holdings fetch."""
    if fund_id:
        fund = db.query(Fund).filter(Fund.id == fund_id).first()
        if not fund:
            return ok({"fetched_count": 0})
        count = fetch_holdings_for_fund(db, fund)
        return ok({"fetched_count": count})

    result = fetch_holdings_for_all_funds(db)
    total = sum(result.values())
    return ok({"fetched_count": total, "detail": result})
