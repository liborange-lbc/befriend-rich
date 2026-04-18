from datetime import date

from app.models.fund import Fund
from app.models.portfolio import PortfolioSnapshot
from app.models.price import FundDailyPrice


def test_overview_empty(client):
    resp = client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_amount_cny"] == 0


def test_overview_with_snapshot(client, db_session):
    db_session.add(PortfolioSnapshot(
        snapshot_date=date(2026, 4, 11),
        total_amount_cny=100000,
        model_breakdown="{}",
    ))
    db_session.add(PortfolioSnapshot(
        snapshot_date=date(2026, 4, 18),
        total_amount_cny=110000,
        model_breakdown="{}",
    ))
    db_session.commit()

    resp = client.get("/api/v1/dashboard/overview")
    data = resp.json()["data"]
    assert data["total_amount_cny"] == 110000
    assert data["change_amount"] == 10000
    assert data["change_pct"] == 10.0


def test_fund_quotes(client, db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    db_session.add(FundDailyPrice(fund_id=fund.id, date=date(2026, 4, 17), close_price=4.0))
    db_session.add(FundDailyPrice(fund_id=fund.id, date=date(2026, 4, 18), close_price=4.1))
    db_session.commit()

    resp = client.get("/api/v1/dashboard/fund-quotes")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["code"] == "510300"
    assert data[0]["change_pct"] == 2.5


def test_recent_alerts_empty(client):
    resp = client.get("/api/v1/dashboard/alerts/recent")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
