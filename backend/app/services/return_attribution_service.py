import logging
from datetime import date
from typing import Any

from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord
from app.models.price import FundDailyPrice

logger = logging.getLogger(__name__)


def _get_records_by_date(db: Session) -> dict[date, list[PortfolioRecord]]:
    """Group all records by record_date, sorted ascending."""
    records = (
        db.query(PortfolioRecord)
        .order_by(asc(PortfolioRecord.record_date))
        .all()
    )
    by_date: dict[date, list[PortfolioRecord]] = {}
    for r in records:
        by_date.setdefault(r.record_date, []).append(r)
    return by_date


def get_attribution_summary(db: Session) -> dict:
    """Overall portfolio return attribution."""
    by_date = _get_records_by_date(db)
    if not by_date:
        return {"total_invested": 0, "current_value": 0, "total_profit": 0, "total_return_pct": None}

    dates = sorted(by_date.keys())
    latest_records = by_date[dates[-1]]

    current_value = sum(r.amount_cny or r.amount for r in latest_records)
    total_profit = sum(r.profit or 0 for r in latest_records)
    total_invested = current_value - total_profit

    # Sum all weekly investments across all dates
    all_records = db.query(PortfolioRecord).all()
    total_weekly_inv = sum(r.weekly_investment or 0 for r in all_records)

    return {
        "current_value": round(current_value, 2),
        "total_invested": round(total_invested, 2),
        "total_profit": round(total_profit, 2),
        "total_return_pct": round(total_profit / total_invested * 100, 2) if total_invested > 0 else None,
        "total_weekly_investments": round(total_weekly_inv, 2),
        "first_date": dates[0].isoformat(),
        "latest_date": dates[-1].isoformat(),
        "weeks_tracked": len(dates),
    }


def get_attribution_by_fund(db: Session) -> list[dict]:
    """Per-fund profit contribution."""
    by_date = _get_records_by_date(db)
    if not by_date:
        return []

    latest_date = max(by_date.keys())
    latest_records = by_date[latest_date]

    total_profit = sum(r.profit or 0 for r in latest_records)
    funds = {f.id: f for f in db.query(Fund).all()}

    results = []
    for r in latest_records:
        fund = funds.get(r.fund_id)
        profit = r.profit or 0
        amount = r.amount_cny or r.amount
        invested = amount - profit

        results.append({
            "fund_id": r.fund_id,
            "fund_code": fund.code if fund else "",
            "fund_name": fund.name if fund else "",
            "channel": r.channel,
            "current_amount": round(amount, 2),
            "profit": round(profit, 2),
            "invested": round(invested, 2),
            "return_pct": round(profit / invested * 100, 2) if invested > 0 else None,
            "contribution_pct": round(profit / total_profit * 100, 2) if total_profit != 0 else 0,
        })

    results.sort(key=lambda x: x["profit"], reverse=True)
    return results


def get_attribution_by_category(db: Session) -> list[dict]:
    """Per-classification-category profit contribution."""
    model = db.query(ClassModel).first()
    if not model:
        return []

    mappings = db.query(FundClassMap).filter(FundClassMap.model_id == model.id).all()
    fund_to_cat: dict[int, int] = {}
    for m in mappings:
        fund_to_cat[m.fund_id] = m.category_id

    categories = {c.id: c.name for c in db.query(ClassCategory).filter(ClassCategory.model_id == model.id).all()}

    by_fund = get_attribution_by_fund(db)
    cat_data: dict[int, dict[str, Any]] = {}
    for item in by_fund:
        cat_id = fund_to_cat.get(item["fund_id"])
        if cat_id is None:
            cat_id = -1
        if cat_id not in cat_data:
            cat_data[cat_id] = {
                "category_id": cat_id,
                "category_name": categories.get(cat_id, "未分类"),
                "current_amount": 0,
                "profit": 0,
                "invested": 0,
                "fund_count": 0,
            }
        cat_data[cat_id]["current_amount"] += item["current_amount"]
        cat_data[cat_id]["profit"] += item["profit"]
        cat_data[cat_id]["invested"] += item["invested"]
        cat_data[cat_id]["fund_count"] += 1

    total_profit = sum(d["profit"] for d in cat_data.values())
    results = []
    for d in cat_data.values():
        d["current_amount"] = round(d["current_amount"], 2)
        d["profit"] = round(d["profit"], 2)
        d["invested"] = round(d["invested"], 2)
        d["return_pct"] = round(d["profit"] / d["invested"] * 100, 2) if d["invested"] > 0 else None
        d["contribution_pct"] = round(d["profit"] / total_profit * 100, 2) if total_profit != 0 else 0
        results.append(d)

    results.sort(key=lambda x: x["profit"], reverse=True)
    return results


def get_twr_curve(db: Session) -> list[dict]:
    """Time-weighted return curve based on weekly snapshots.

    TWR formula per period: R_t = (V_end - CF) / V_start - 1
    where CF = weekly_investment inflows during the period.
    """
    by_date = _get_records_by_date(db)
    if len(by_date) < 2:
        return []

    dates = sorted(by_date.keys())
    cumulative = 1.0
    curve = [{"date": dates[0].isoformat(), "twr": 0.0}]

    for i in range(1, len(dates)):
        prev_total = sum(r.amount_cny or r.amount for r in by_date[dates[i - 1]])
        curr_total = sum(r.amount_cny or r.amount for r in by_date[dates[i]])
        cash_flow = sum(r.weekly_investment or 0 for r in by_date[dates[i]])

        if prev_total > 0:
            period_return = (curr_total - cash_flow) / prev_total - 1
            cumulative *= (1 + period_return)

        curve.append({
            "date": dates[i].isoformat(),
            "twr": round((cumulative - 1) * 100, 4),
        })

    return curve
