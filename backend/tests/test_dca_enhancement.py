"""Tests for DCA strategy enhancements."""

from datetime import date, timedelta

import pandas as pd

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.services.backtest.engine import _evaluate_buy, _evaluate_sell, run_backtest


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_prices(db, fund_id: int, count: int = 50):
    """Seed prices with varying deviations."""
    base = date.today() - timedelta(days=count)
    for i in range(count):
        db.add(FundDailyPrice(
            fund_id=fund_id,
            date=base + timedelta(days=i),
            close_price=1.0 + i * 0.01,
            dev_60=-15 + i * 0.5,  # goes from -15 to +10 over 50 days
        ))
    db.commit()


class TestSmartDCA:
    def test_smart_dca_low_deviation(self):
        """When deviation is very negative, should buy 1.5x."""
        config = {"type": "smart_dca", "amount": 1000, "interval": "daily", "field": "dev_60"}
        row = pd.Series({"close": 1.0, "dev_60": -12})
        amount = _evaluate_buy(config, row, 0)
        assert amount == 1500.0

    def test_smart_dca_normal_deviation(self):
        """When deviation is near zero, should buy 1.0x."""
        config = {"type": "smart_dca", "amount": 1000, "interval": "daily", "field": "dev_60"}
        row = pd.Series({"close": 1.0, "dev_60": 0})
        amount = _evaluate_buy(config, row, 0)
        assert amount == 1000.0

    def test_smart_dca_high_deviation(self):
        """When deviation is very positive, should buy 0.5x."""
        config = {"type": "smart_dca", "amount": 1000, "interval": "daily", "field": "dev_60"}
        row = pd.Series({"close": 1.0, "dev_60": 15})
        amount = _evaluate_buy(config, row, 0)
        assert amount == 500.0

    def test_smart_dca_respects_interval(self):
        """Should only buy on interval days."""
        config = {"type": "smart_dca", "amount": 1000, "interval": "weekly", "field": "dev_60"}
        row = pd.Series({"close": 1.0, "dev_60": 0})
        # idx=0 should trigger, idx=1 should not
        assert _evaluate_buy(config, row, 0) == 1000.0
        assert _evaluate_buy(config, row, 1) == 0.0


class TestLadderSell:
    def test_ladder_partial_sell(self):
        """At 10% return, should sell 30%."""
        config = {"type": "ladder", "tiers": [
            {"return": 0.10, "sell_pct": 0.30},
            {"return": 0.20, "sell_pct": 0.30},
            {"return": 0.30, "sell_pct": 1.00},
        ]}
        row = pd.Series({"close": 1.10})  # 10% up from invested=1.0 per share
        fraction = _evaluate_sell(config, row, shares=100, invested=100)
        assert fraction == 0.30

    def test_ladder_stop_loss(self):
        config = {"type": "ladder", "stop_loss": -0.10}
        row = pd.Series({"close": 0.85})
        fraction = _evaluate_sell(config, row, shares=100, invested=100)
        assert fraction == 1.0

    def test_ladder_no_trigger(self):
        config = {"type": "ladder", "tiers": [{"return": 0.10, "sell_pct": 0.30}]}
        row = pd.Series({"close": 1.05})  # only 5% up
        fraction = _evaluate_sell(config, row, shares=100, invested=100)
        assert fraction == 0.0


class TestBacktestIntegration:
    def test_smart_dca_backtest(self, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300")
        _seed_prices(db_session, fund.id, 50)

        config = {
            "buy": {"type": "smart_dca", "amount": 1000, "interval": "weekly", "field": "dev_60"},
            "sell": {},
        }
        result = run_backtest(
            db_session, fund.id, config,
            date.today() - timedelta(days=50),
            date.today(),
        )
        assert "error" not in result
        assert len(result["trade_log"]) > 0
        # Smart DCA should have variable amounts
        buy_amounts = [t["amount"] for t in result["trade_log"] if t["action"] == "buy"]
        assert len(set(buy_amounts)) > 1  # not all the same

    def test_portfolio_backtest_api(self, client, db_session):
        f1 = _seed_fund(db_session, "510300", "沪深300")
        f2 = _seed_fund(db_session, "510500", "中证500")
        _seed_prices(db_session, f1.id, 30)
        _seed_prices(db_session, f2.id, 30)

        resp = client.post("/api/v1/backtest/portfolio", json={
            "items": [
                {"fund_id": f1.id, "config": {"buy": {"type": "dca", "amount": 500, "interval": "weekly"}, "sell": {}}},
                {"fund_id": f2.id, "config": {"buy": {"type": "dca", "amount": 500, "interval": "weekly"}, "sell": {}}},
            ],
            "start_date": (date.today() - timedelta(days=30)).isoformat(),
            "end_date": date.today().isoformat(),
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["fund_count"] == 2
        assert len(data["equity_curve"]) > 0
        assert data["metrics"]["total_return"] is not None
