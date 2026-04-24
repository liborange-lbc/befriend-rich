"""Tests for fund comparison and risk stats feature."""

import math
from datetime import date, timedelta

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.services.fund_stats_service import (
    _annualized_return,
    _daily_returns,
    _max_drawdown,
    _sharpe_ratio,
    _volatility,
)


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_prices(db, fund_id: int, prices: list[float], start_date: date | None = None):
    """Seed daily prices going back from today."""
    base = start_date or date.today()
    for i, price in enumerate(prices):
        db.add(FundDailyPrice(
            fund_id=fund_id,
            date=base - timedelta(days=len(prices) - 1 - i),
            close_price=price,
        ))
    db.commit()


class TestMetricCalculations:
    def test_daily_returns(self):
        prices = [100, 102, 101, 105]
        returns = _daily_returns(prices)
        assert len(returns) == 3
        assert abs(returns[0] - 0.02) < 1e-10
        assert abs(returns[1] - (101 / 102 - 1)) < 1e-10

    def test_annualized_return(self):
        # Doubled in 242 trading days = 100% annual return
        prices = [1.0] + [1.0 + i * (1.0 / 241) for i in range(1, 242)]
        prices[-1] = 2.0  # exact doubling
        result = _annualized_return(prices)
        assert result is not None
        assert abs(result - 1.0) < 0.01  # ~100%

    def test_max_drawdown(self):
        prices = [100, 110, 90, 95, 80, 100]
        result = _max_drawdown(prices)
        # Peak was 110, lowest after was 80 → drawdown = 30/110 ≈ 0.2727
        assert result is not None
        assert abs(result - 30 / 110) < 1e-6

    def test_max_drawdown_no_drawdown(self):
        prices = [100, 101, 102, 103]
        result = _max_drawdown(prices)
        assert result == 0.0

    def test_volatility(self):
        # Constant returns = zero volatility
        prices = [100, 101, 102, 103, 104]
        returns = _daily_returns(prices)
        vol = _volatility(returns)
        assert vol is not None
        assert vol < 0.05  # near zero

    def test_sharpe_ratio(self):
        # High positive returns with small variance = high Sharpe
        returns = [0.01 + (i % 3) * 0.001 for i in range(100)]
        sr = _sharpe_ratio(returns)
        assert sr is not None
        assert sr > 5  # very high Sharpe

    def test_empty_prices(self):
        assert _annualized_return([]) is None
        assert _max_drawdown([]) is None
        assert _volatility([]) is None
        assert _sharpe_ratio([]) is None


class TestFundCompareAPI:
    def test_stats_endpoint(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        prices = [1.0 + i * 0.01 for i in range(50)]
        _seed_prices(db_session, fund.id, prices)

        resp = client.get("/api/v1/fund-compare/stats")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["fund_code"] == "510300"
        assert data[0]["annualized_return"] is not None
        assert data[0]["max_drawdown"] is not None
        assert data[0]["volatility"] is not None
        assert data[0]["sharpe_ratio"] is not None

    def test_normalized_prices(self, client, db_session):
        fund1 = _seed_fund(db_session, "510300", "沪深300ETF")
        fund2 = _seed_fund(db_session, "510500", "中证500ETF")
        _seed_prices(db_session, fund1.id, [1.0, 1.1, 1.2])
        _seed_prices(db_session, fund2.id, [2.0, 2.2, 2.5])

        resp = client.get(f"/api/v1/fund-compare/prices?fund_ids={fund1.id},{fund2.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert str(fund1.id) in data
        assert str(fund2.id) in data
        # First value should be 1.0 (normalized)
        assert data[str(fund1.id)][0]["value"] == 1.0
        assert data[str(fund2.id)][0]["value"] == 1.0

    def test_stats_empty(self, client, db_session):
        _seed_fund(db_session, "510300", "沪深300ETF")
        # No prices seeded
        resp = client.get("/api/v1/fund-compare/stats")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
