from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord, PortfolioSnapshot
from app.models.price import FundDailyPrice
from app.models.strategy import AlertLog
from app.response import ok

router = APIRouter()


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    latest_snapshot = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.snapshot_date.desc())
        .first()
    )
    prev_snapshot = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.snapshot_date.desc())
        .offset(1)
        .first()
    )

    total = latest_snapshot.total_amount_cny if latest_snapshot else 0
    prev_total = prev_snapshot.total_amount_cny if prev_snapshot else 0
    change = total - prev_total
    change_pct = (change / prev_total * 100) if prev_total > 0 else 0

    from app.services.market_data.exchange_rate import get_latest_rate
    return ok({
        "total_amount_cny": round(total, 2),
        "change_amount": round(change, 2),
        "change_pct": round(change_pct, 2),
        "latest_date": latest_snapshot.snapshot_date.isoformat() if latest_snapshot else None,
        "usd_cny_rate": get_latest_rate(db, "USD/CNY"),
        "hkd_cny_rate": get_latest_rate(db, "HKD/CNY"),
    })


@router.get("/fund-quotes")
def get_fund_quotes(db: Session = Depends(get_db)):
    funds = db.query(Fund).filter(Fund.is_active == True).all()
    result = []
    for fund in funds:
        latest = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund.id)
            .order_by(FundDailyPrice.date.desc())
            .first()
        )
        prev = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund.id)
            .order_by(FundDailyPrice.date.desc())
            .offset(1)
            .first()
        )
        if latest:
            prev_close = prev.close_price if prev else latest.close_price
            change_pct = (latest.close_price - prev_close) / prev_close * 100 if prev_close else 0
            result.append({
                "fund_id": fund.id,
                "code": fund.code,
                "name": fund.name,
                "close_price": latest.close_price,
                "change_pct": round(change_pct, 2),
                "date": latest.date.isoformat(),
            })
    return ok(result)


@router.get("/alerts/recent")
def get_recent_alerts(db: Session = Depends(get_db)):
    alerts = db.query(AlertLog).order_by(AlertLog.id.desc()).limit(10).all()
    result = []
    for a in alerts:
        fund = db.query(Fund).filter(Fund.id == a.fund_id).first()
        result.append({
            "id": a.id,
            "fund_name": fund.name if fund else "",
            "triggered_at": a.triggered_at,
            "condition_desc": a.condition_desc,
            "current_values": a.current_values,
        })
    return ok(result)
