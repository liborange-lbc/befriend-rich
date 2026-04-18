import json
from datetime import date
from unittest.mock import patch

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.models.strategy import AlertLog, Strategy
from app.services.strategy.evaluator import run_strategy_check


def test_strategy_check_triggers_alert(db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(
        name="低估买入",
        fund_id=fund.id,
        type="condition",
        alert_enabled=True,
        alert_conditions=json.dumps([
            {"field": "dev_60", "operator": "<", "threshold": -5}
        ]),
    )
    db_session.add(strategy)
    db_session.commit()

    db_session.add(FundDailyPrice(
        fund_id=fund.id,
        date=date(2026, 4, 18),
        close_price=3.8,
        dev_60=-8.5,
    ))
    db_session.commit()

    with patch("app.services.strategy.evaluator.send_feishu_card_message", return_value=False):
        run_strategy_check(db_session)

    alerts = db_session.query(AlertLog).all()
    assert len(alerts) == 1
    assert alerts[0].strategy_id == strategy.id


def test_strategy_check_no_trigger(db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(
        name="低估买入",
        fund_id=fund.id,
        type="condition",
        alert_enabled=True,
        alert_conditions=json.dumps([
            {"field": "dev_60", "operator": "<", "threshold": -5}
        ]),
    )
    db_session.add(strategy)
    db_session.commit()

    db_session.add(FundDailyPrice(
        fund_id=fund.id,
        date=date(2026, 4, 18),
        close_price=4.5,
        dev_60=2.0,
    ))
    db_session.commit()

    with patch("app.services.strategy.evaluator.send_feishu_card_message", return_value=False):
        run_strategy_check(db_session)

    alerts = db_session.query(AlertLog).all()
    assert len(alerts) == 0


def test_strategy_check_or_logic(db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(
        name="多条件",
        fund_id=fund.id,
        type="condition",
        alert_enabled=True,
        alert_conditions=json.dumps({
            "logic": "or",
            "items": [
                {"field": "dev_30", "operator": "<", "threshold": -10},
                {"field": "dev_60", "operator": "<", "threshold": -5},
            ],
        }),
    )
    db_session.add(strategy)
    db_session.commit()

    db_session.add(FundDailyPrice(
        fund_id=fund.id,
        date=date(2026, 4, 18),
        close_price=4.0,
        dev_30=-2.0,
        dev_60=-8.0,
    ))
    db_session.commit()

    with patch("app.services.strategy.evaluator.send_feishu_card_message", return_value=False):
        run_strategy_check(db_session)

    alerts = db_session.query(AlertLog).all()
    assert len(alerts) == 1


def test_strategy_disabled_no_check(db_session):
    fund = Fund(code="510300", name="沪深300", currency="CNY", data_source="tushare")
    db_session.add(fund)
    db_session.commit()

    strategy = Strategy(
        name="禁用策略",
        fund_id=fund.id,
        type="condition",
        alert_enabled=False,
        alert_conditions=json.dumps([
            {"field": "dev_60", "operator": "<", "threshold": -5}
        ]),
    )
    db_session.add(strategy)
    db_session.commit()

    db_session.add(FundDailyPrice(
        fund_id=fund.id,
        date=date(2026, 4, 18),
        close_price=3.8,
        dev_60=-8.5,
    ))
    db_session.commit()

    with patch("app.services.strategy.evaluator.send_feishu_card_message", return_value=False):
        run_strategy_check(db_session)

    alerts = db_session.query(AlertLog).all()
    assert len(alerts) == 0
