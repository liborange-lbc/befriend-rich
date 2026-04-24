from pydantic import BaseModel


class FundHoldingResponse(BaseModel):
    id: int
    fund_id: int
    fund_code: str | None = None
    fund_name: str | None = None
    quarter: str
    stock_code: str
    stock_name: str
    holding_ratio: float | None = None
    holding_shares: float | None = None
    holding_value: float | None = None
    disclosure_date: str | None = None

    model_config = {"from_attributes": True}
