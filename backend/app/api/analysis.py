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
