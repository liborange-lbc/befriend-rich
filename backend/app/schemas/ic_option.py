from datetime import date

from pydantic import BaseModel


class ICPriceItem(BaseModel):
    date: date
    contract_type: str
    close_price: float
    contract_code: str | None = None

    model_config = {"from_attributes": True}


class ICPriceRow(BaseModel):
    """One date, all five series."""

    date: date
    index: float | None = None
    current_month: float | None = None
    next_month: float | None = None
    current_quarter: float | None = None
    next_quarter: float | None = None


class ICStatRow(BaseModel):
    """Statistics for one contract type."""

    contract_type: str
    label: str
    spread_current: float | None = None
    annual_current: float | None = None
    annual_1m: float | None = None
    annual_1y: float | None = None
    annual_3y: float | None = None
    annual_all: float | None = None


class ICPositionCalc(BaseModel):
    entry_point: float
    entry_capital: float
    margin_rate: float
    multiplier: int = 200
    contract_value: float
    margin_per_contract: float
    num_contracts: int
    total_margin: float
    remaining_capital: float
    margin_call_point: float
    liquidation_point: float
