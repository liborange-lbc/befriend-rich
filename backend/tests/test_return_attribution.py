"""Tests for return attribution feature."""

from datetime import date, timedelta

from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_records(db, fund_id: int, weeks: list[tuple[float, float, float | None]]):
    """Seed weekly portfolio records. Each tuple: (amount, profit, weekly_investment)."""
    base = date.today() - timedelta(weeks=len(weeks))
    for i, (amount, profit, inv) in enumerate(weeks):
        record_date = base + timedelta(weeks=i)
        # Normalize to Monday
        record_date = record_date - timedelta(days=record_date.weekday())
        db.add(PortfolioRecord(
            fund_id=fund_id,
            record_date=record_date,
            amount=amount,
            amount_cny=amount,
            profit=profit,
            channel="微众银行",
            weekly_investment=inv,
        ))
    db.commit()


class TestAttributionSummary:
    def test_basic_summary(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        # 4 weeks: invested 1000, grew to 1100 (profit=100)
        _seed_records(db_session, fund.id, [
            (1000, 0, 1000),
            (1020, 20, None),
            (1050, 50, None),
            (1100, 100, None),
        ])

        resp = client.get("/api/v1/attribution/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["current_value"] == 1100
        assert data["total_profit"] == 100
        assert data["weeks_tracked"] == 4

    def test_empty(self, client, db_session):
        resp = client.get("/api/v1/attribution/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_invested"] == 0


class TestAttributionByFund:
    def test_two_funds(self, client, db_session):
        f1 = _seed_fund(db_session, "510300", "沪深300")
        f2 = _seed_fund(db_session, "510500", "中证500")
        _seed_records(db_session, f1.id, [(1000, 0, 1000), (1100, 100, None)])
        _seed_records(db_session, f2.id, [(500, 0, 500), (450, -50, None)])

        resp = client.get("/api/v1/attribution/by-fund")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # Sorted by profit desc
        assert data[0]["profit"] == 100
        assert data[1]["profit"] == -50


class TestTWRCurve:
    def test_twr_no_cashflow(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300")
        # Pure growth: 1000 → 1050 → 1100 (no new investment)
        _seed_records(db_session, fund.id, [
            (1000, 0, 1000),   # initial
            (1050, 50, None),  # +5%
            (1100, 100, None), # +4.76%
        ])

        resp = client.get("/api/v1/attribution/twr")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        assert data[0]["twr"] == 0.0  # start
        assert data[-1]["twr"] > 0    # positive TWR

    def test_twr_with_cashflow(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300")
        # Week 1: start 1000, Week 2: add 500 → 1520 (1000 grew to 1020, then +500)
        _seed_records(db_session, fund.id, [
            (1000, 0, 1000),
            (1520, 20, 500),   # weekly_investment=500
        ])

        resp = client.get("/api/v1/attribution/twr")
        data = resp.json()["data"]
        assert len(data) == 2
        # TWR should reflect only the organic growth: (1520-500)/1000 - 1 = 2%
        assert abs(data[1]["twr"] - 2.0) < 0.1
