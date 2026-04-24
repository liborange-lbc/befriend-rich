"""Tests for correlation analysis feature."""

from datetime import date, timedelta

from app.models.fund import Fund
from app.models.fund_holding import FundHolding
from app.models.price import FundDailyPrice
from app.services.correlation_service import _pearson


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_daily_prices(db, fund_id: int, prices: list[float]):
    """Seed prices going back from today."""
    today = date.today()
    for i, p in enumerate(prices):
        db.add(FundDailyPrice(
            fund_id=fund_id,
            date=today - timedelta(days=len(prices) - 1 - i),
            close_price=p,
        ))
    db.commit()


def _seed_holdings(db, fund_id: int, stocks: list[str], quarter: str = "2024Q4"):
    for code in stocks:
        db.add(FundHolding(
            fund_id=fund_id,
            quarter=quarter,
            stock_code=code,
            stock_name=f"Stock {code}",
            holding_ratio=5.0,
        ))
    db.commit()


class TestPearson:
    def test_perfect_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        assert abs(_pearson(xs, ys) - 1.0) < 1e-10

    def test_negative_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        ys = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        assert abs(_pearson(xs, ys) - (-1.0)) < 1e-10

    def test_insufficient_data(self):
        assert _pearson([1, 2, 3], [4, 5, 6]) is None


class TestCorrelationMatrix:
    def test_matrix_structure(self, client, db_session):
        f1 = _seed_fund(db_session, "510300", "沪深300")
        f2 = _seed_fund(db_session, "510500", "中证500")
        # Similar upward trend
        prices1 = [1.0 + i * 0.01 + (i % 3) * 0.005 for i in range(50)]
        prices2 = [2.0 + i * 0.02 + (i % 5) * 0.003 for i in range(50)]
        _seed_daily_prices(db_session, f1.id, prices1)
        _seed_daily_prices(db_session, f2.id, prices2)

        resp = client.get("/api/v1/correlation/matrix")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["labels"]) == 2
        assert len(data["matrix"]) == 2
        # Diagonal should be 1.0
        assert data["matrix"][0][0] == 1.0
        assert data["matrix"][1][1] == 1.0
        # Off-diagonal should be a valid correlation
        assert data["matrix"][0][1] is not None
        assert -1.0 <= data["matrix"][0][1] <= 1.0


class TestHoldingOverlap:
    def test_full_overlap(self, client, db_session):
        f1 = _seed_fund(db_session, "510300", "沪深300")
        f2 = _seed_fund(db_session, "510500", "中证500")
        _seed_holdings(db_session, f1.id, ["000001", "000002", "000003"])
        _seed_holdings(db_session, f2.id, ["000001", "000002", "000003"])

        resp = client.get("/api/v1/correlation/overlap")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["matrix"][0][1] == 1.0  # identical holdings

    def test_partial_overlap(self, client, db_session):
        f1 = _seed_fund(db_session, "510300", "沪深300")
        f2 = _seed_fund(db_session, "510500", "中证500")
        _seed_holdings(db_session, f1.id, ["000001", "000002"])
        _seed_holdings(db_session, f2.id, ["000002", "000003"])

        resp = client.get("/api/v1/correlation/overlap")
        data = resp.json()["data"]
        # Jaccard: intersection=1, union=3 → 1/3
        assert abs(data["matrix"][0][1] - 1 / 3) < 0.01


class TestDiversificationScore:
    def test_score_endpoint(self, client, db_session):
        f1 = _seed_fund(db_session, "510300", "沪深300")
        f2 = _seed_fund(db_session, "510500", "中证500")
        prices1 = [1.0 + i * 0.01 + (i % 3) * 0.005 for i in range(50)]
        prices2 = [2.0 + i * 0.02 + (i % 5) * 0.003 for i in range(50)]
        _seed_daily_prices(db_session, f1.id, prices1)
        _seed_daily_prices(db_session, f2.id, prices2)

        resp = client.get("/api/v1/correlation/diversification-score")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["fund_count"] == 2
        assert data["score"] is not None
        assert 0 <= data["score"] <= 2  # score = 1 - avg_corr, range [-1, 2]
