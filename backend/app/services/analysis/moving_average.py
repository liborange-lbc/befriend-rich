import logging
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.models.price import FundDailyPrice

logger = logging.getLogger(__name__)

MA_PERIODS = [30, 60, 90, 120, 180, 360]


def calculate_and_store_indicators(db: Session, fund_id: int):
    prices = (
        db.query(FundDailyPrice)
        .filter(FundDailyPrice.fund_id == fund_id)
        .order_by(FundDailyPrice.date)
        .all()
    )
    if not prices:
        return

    df = pd.DataFrame(
        [{"id": p.id, "date": p.date, "close": p.close_price} for p in prices]
    )
    df = df.sort_values("date").reset_index(drop=True)

    for period in MA_PERIODS:
        col = f"ma_{period}"
        dev_col = f"dev_{period}"
        df[col] = df["close"].rolling(window=period, min_periods=period).mean()
        df[dev_col] = ((df["close"] - df[col]) / df[col] * 100).where(df[col].notna())

    for _, row in df.iterrows():
        price = db.query(FundDailyPrice).filter(FundDailyPrice.id == row["id"]).first()
        if price:
            for period in MA_PERIODS:
                ma_val = row[f"ma_{period}"]
                dev_val = row[f"dev_{period}"]
                setattr(price, f"ma_{period}", None if pd.isna(ma_val) else round(float(ma_val), 4))
                setattr(price, f"dev_{period}", None if pd.isna(dev_val) else round(float(dev_val), 4))

    db.commit()
