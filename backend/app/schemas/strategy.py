from datetime import date

from pydantic import BaseModel, Field


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    fund_id: int | None = None
    type: str = Field(default="dca", max_length=30)
    config: str = "{}"
    alert_enabled: bool = True
    alert_conditions: str = "[]"


class StrategyUpdate(BaseModel):
    name: str | None = None
    fund_id: int | None = None
    type: str | None = None
    config: str | None = None
    alert_enabled: bool | None = None
    alert_conditions: str | None = None
    is_active: bool | None = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    fund_id: int | None
    type: str
    config: str
    alert_enabled: bool
    alert_conditions: str
    is_active: bool

    model_config = {"from_attributes": True}


class BacktestRequest(BaseModel):
    strategy_id: int
    fund_id: int
    start_date: date
    end_date: date


class BacktestResultResponse(BaseModel):
    id: int
    strategy_id: int
    fund_id: int
    start_date: date
    end_date: date
    total_return: float | None
    annual_return: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    volatility: float | None
    win_rate: float | None
    profit_loss_ratio: float | None
    trade_log: str
    equity_curve: str

    model_config = {"from_attributes": True}


class AlertLogResponse(BaseModel):
    id: int
    strategy_id: int
    fund_id: int | None
    triggered_at: str
    condition_desc: str
    current_values: str
    notified: bool

    model_config = {"from_attributes": True}
