from pydantic import BaseModel, Field


class FundCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    currency: str = Field(default="CNY", max_length=10)
    data_source: str = Field(default="tushare", max_length=20)
    fee_rate: float = Field(default=0.0, ge=0.0)


class FundUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    currency: str | None = None
    data_source: str | None = None
    fee_rate: float | None = None
    is_active: bool | None = None


class FundResponse(BaseModel):
    id: int
    code: str
    name: str
    currency: str
    data_source: str
    fee_rate: float
    is_active: bool

    model_config = {"from_attributes": True}
