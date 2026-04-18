import json
from datetime import date, timedelta

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.models.strategy import Strategy


def test_run_backtest_dca(client, db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(
        name="DCA策略",
        fund_id=fund.id,
        type="dca",
        config=json.dumps({"buy": {"type": "dca", "amount": 1000, "interval": "daily"}}),
    )
    db_session.add(strategy)
    db_session.commit()

    base_date = date(2024, 1, 1)
    for i in range(30):
        db_session.add(FundDailyPrice(
            fund_id=fund.id,
            date=base_date + timedelta(days=i),
            close_price=100 + i * 0.5,
        ))
    db_session.commit()

    resp = client.post("/api/v1/backtest/run", json={
        "strategy_id": strategy.id,
        "fund_id": fund.id,
        "start_date": "2024-01-01",
        "end_date": "2024-01-30",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_return"] is not None
    assert data["trade_log"] is not None


def test_run_backtest_no_data(client, db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(name="DCA策略", fund_id=fund.id, type="dca", config="{}")
    db_session.add(strategy)
    db_session.commit()

    resp = client.post("/api/v1/backtest/run", json={
        "strategy_id": strategy.id,
        "fund_id": fund.id,
        "start_date": "2024-01-01",
        "end_date": "2024-01-30",
    })
    assert resp.status_code == 400


def test_list_backtest_results(client, db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(
        name="DCA策略",
        fund_id=fund.id,
        type="dca",
        config=json.dumps({"buy": {"type": "dca", "amount": 1000, "interval": "daily"}}),
    )
    db_session.add(strategy)
    db_session.commit()

    base_date = date(2024, 1, 1)
    for i in range(30):
        db_session.add(FundDailyPrice(
            fund_id=fund.id,
            date=base_date + timedelta(days=i),
            close_price=100 + i * 0.5,
        ))
    db_session.commit()

    client.post("/api/v1/backtest/run", json={
        "strategy_id": strategy.id,
        "fund_id": fund.id,
        "start_date": "2024-01-01",
        "end_date": "2024-01-30",
    })

    resp = client.get("/api/v1/backtest/results")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def test_backtest_strategy_not_found(client):
    resp = client.post("/api/v1/backtest/run", json={
        "strategy_id": 999,
        "fund_id": 1,
        "start_date": "2024-01-01",
        "end_date": "2024-01-30",
    })
    assert resp.status_code == 404
