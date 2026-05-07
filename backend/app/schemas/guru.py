from pydantic import BaseModel


class HoldingItem(BaseModel):
    id: int
    stock_code: str | None = None
    stock_name: str | None = None
    position_change: str | None = None
    trade_impact_pct: str | None = None
    shares: str | None = None
    value: str | None = None
    weight_pct: str | None = None
    ownership_pct: str | None = None
    sector: str | None = None
    market_cap: str | None = None
    return_3m_pct: str | None = None
    return_ytd_pct: str | None = None

    model_config = {"from_attributes": True}


class TradeItem(BaseModel):
    id: int
    stock_code: str | None = None
    stock_name: str | None = None
    action: str | None = None
    shares_changed: str | None = None
    price: str | None = None
    value: str | None = None
    trade_date: str | None = None
    report_date: str | None = None
    current_shares: str | None = None

    model_config = {"from_attributes": True}


class GuruBase(BaseModel):
    id: int
    name: str
    name_en: str | None = None
    slug: str
    category: str | None = None
    num_holdings: int = 0
    num_trades: int = 0

    model_config = {"from_attributes": True}


class GuruList(BaseModel):
    gurus: list[GuruBase]
    total: int


class GuruDetail(GuruBase):
    description: str | None = None


class GuruStockBase(BaseModel):
    id: int
    code: str | None = None
    name: str | None = None
    market: str | None = None
    sector: str | None = None
    guru_count: int = 0

    model_config = {"from_attributes": True}


class GuruStockDetail(GuruStockBase):
    pass
