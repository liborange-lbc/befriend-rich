from datetime import date

from pydantic import BaseModel


class FundDailyPriceResponse(BaseModel):
    id: int
    fund_id: int
    date: date
    close_price: float
    ma_30: float | None
    ma_60: float | None
    ma_90: float | None
    ma_120: float | None
    ma_180: float | None
    ma_360: float | None
    dev_30: float | None
    dev_60: float | None
    dev_90: float | None
    dev_120: float | None
    dev_180: float | None
    dev_360: float | None

    model_config = {"from_attributes": True}


class ExchangeRateResponse(BaseModel):
    id: int
    date: date
    pair: str
    rate: float

    model_config = {"from_attributes": True}


class DeviationSummaryItem(BaseModel):
    fund_id: int
    fund_name: str
    fund_code: str
    date: date
    close_price: float
    dev_30: float | None
    dev_60: float | None
    dev_90: float | None
    dev_120: float | None
    dev_180: float | None
    dev_360: float | None
