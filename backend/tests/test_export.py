"""Tests for data export feature."""

from datetime import date, timedelta

from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord
from app.models.price import FundDailyPrice


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


class TestPortfolioCSV:
    def test_export_csv(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        today = date.today() - timedelta(days=date.today().weekday())
        db_session.add(PortfolioRecord(fund_id=fund.id, record_date=today, amount=10000, amount_cny=10000, channel="微众银行", profit=500))
        db_session.commit()

        resp = client.get("/api/v1/export/portfolio-csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "510300" in content
        assert "沪深300ETF" in content
        assert "10000" in content

    def test_empty_csv(self, client, db_session):
        resp = client.get("/api/v1/export/portfolio-csv")
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # header only


class TestFundStatsCSV:
    def test_export_stats_csv(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        for i in range(50):
            db_session.add(FundDailyPrice(
                fund_id=fund.id,
                date=date.today() - timedelta(days=50 - i),
                close_price=1.0 + i * 0.01,
            ))
        db_session.commit()

        resp = client.get("/api/v1/export/fund-stats-csv")
        assert resp.status_code == 200
        assert "510300" in resp.text


class TestReport:
    def test_report_structure(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        today = date.today() - timedelta(days=date.today().weekday())
        db_session.add(PortfolioRecord(fund_id=fund.id, record_date=today, amount=10000, amount_cny=10000, channel="微众银行", profit=500))
        db_session.commit()

        resp = client.get("/api/v1/export/report")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "report_date" in data
        assert "overview" in data
        assert "top_performers" in data
        assert "by_fund" in data

    def test_empty_report(self, client, db_session):
        resp = client.get("/api/v1/export/report")
        assert resp.status_code == 200
