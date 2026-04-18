from datetime import date, timedelta

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.services.analysis.moving_average import calculate_and_store_indicators


def test_moving_average_calculation(db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    base_date = date(2024, 1, 1)
    for i in range(40):
        db_session.add(FundDailyPrice(
            fund_id=fund.id,
            date=base_date + timedelta(days=i),
            close_price=100 + i * 0.5,
        ))
    db_session.commit()

    calculate_and_store_indicators(db_session, fund.id)

    prices = (
        db_session.query(FundDailyPrice)
        .filter(FundDailyPrice.fund_id == fund.id)
        .order_by(FundDailyPrice.date)
        .all()
    )

    last_price = prices[-1]
    assert last_price.ma_30 is not None
    assert last_price.dev_30 is not None
    assert last_price.ma_60 is None  # not enough data for MA60

    assert prices[0].ma_30 is None  # not enough data for first entries


def test_deviation_summary_api(client, db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    db_session.add(FundDailyPrice(
        fund_id=fund.id,
        date=date(2026, 4, 18),
        close_price=4.012,
        dev_30=2.5,
        dev_60=-1.3,
    ))
    db_session.commit()

    resp = client.get("/api/v1/analysis/deviation-summary")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["fund_code"] == "510300"
    assert data[0]["dev_30"] == 2.5
