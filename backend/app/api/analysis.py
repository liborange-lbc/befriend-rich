from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.response import ok
from app.schemas.price import DeviationSummaryItem, FundDailyPriceResponse

router = APIRouter()


@router.get("/prices/{fund_id}")
def get_fund_prices(
    fund_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(FundDailyPrice).filter(FundDailyPrice.fund_id == fund_id)
    if start_date:
        query = query.filter(FundDailyPrice.date >= start_date)
    if end_date:
        query = query.filter(FundDailyPrice.date <= end_date)
    prices = query.order_by(FundDailyPrice.date).all()
    return ok([FundDailyPriceResponse.model_validate(p).model_dump() for p in prices])


@router.get("/ma-timing/{fund_id}")
def get_ma_timing(
    fund_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """均线择时数据：返回收盘价、250日均线、偏离度及策略状态。"""
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        return ok(None)

    query = db.query(FundDailyPrice).filter(FundDailyPrice.fund_id == fund_id)
    if start_date:
        query = query.filter(FundDailyPrice.date >= start_date)
    if end_date:
        query = query.filter(FundDailyPrice.date <= end_date)
    prices = query.order_by(FundDailyPrice.date).all()

    history = [
        {
            "date": str(p.date),
            "close_price": p.close_price,
            "ma_250": p.ma_250,
            "dev_250": p.dev_250,
        }
        for p in prices
    ]

    # Latest status
    latest_entry = prices[-1] if prices else None
    latest = None
    if latest_entry:
        dev = latest_entry.dev_250
        if dev is not None:
            if dev < 0:
                status, status_label, color = "buy", "定投买入", "green"
            elif dev >= 10:
                status, status_label, color = "sell", "分批卖出", "red"
            else:
                status, status_label, color = "hold", "持仓不动", "yellow"
        else:
            status, status_label, color = "unknown", "数据不足", "gray"

        latest = {
            "date": str(latest_entry.date),
            "close_price": latest_entry.close_price,
            "ma_250": latest_entry.ma_250,
            "dev_250": latest_entry.dev_250,
            "status": status,
            "status_label": status_label,
            "color": color,
        }

    return ok({
        "fund_id": fund.id,
        "fund_name": fund.name,
        "fund_code": fund.code,
        "latest": latest,
        "history": history,
    })


@router.get("/deviation-summary")
def get_deviation_summary(db: Session = Depends(get_db)):
    funds = db.query(Fund).filter(Fund.is_active == True).all()
    result = []
    for fund in funds:
        latest = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund.id)
            .order_by(FundDailyPrice.date.desc())
            .first()
        )
        if latest:
            result.append(
                DeviationSummaryItem(
                    fund_id=fund.id,
                    fund_name=fund.name,
                    fund_code=fund.code,
                    date=latest.date,
                    close_price=latest.close_price,
                    dev_30=latest.dev_30,
                    dev_60=latest.dev_60,
                    dev_90=latest.dev_90,
                    dev_120=latest.dev_120,
                    dev_180=latest.dev_180,
                    dev_360=latest.dev_360,
                ).model_dump()
            )
    return ok(result)
