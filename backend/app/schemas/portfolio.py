from datetime import date

from pydantic import BaseModel, Field


class PortfolioRecordCreate(BaseModel):
    fund_id: int
    record_date: date
    amount: float = Field(..., gt=0)
    profit: float | None = 0.0


class PortfolioRecordBatchCreate(BaseModel):
    records: list[PortfolioRecordCreate]


class PortfolioRecordUpdate(BaseModel):
    amount: float | None = None
    profit: float | None = None


class PortfolioRecordResponse(BaseModel):
    id: int
    fund_id: int
    record_date: date
    amount: float
    amount_cny: float
    profit: float | None

    model_config = {"from_attributes": True}


class PortfolioSnapshotResponse(BaseModel):
    id: int
    snapshot_date: date
    total_amount_cny: float
    model_breakdown: str

    model_config = {"from_attributes": True}
