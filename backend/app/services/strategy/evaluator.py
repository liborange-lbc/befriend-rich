import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.models.strategy import AlertLog, Strategy
from app.services.notification.feishu import send_feishu_card_message

logger = logging.getLogger(__name__)


def run_strategy_check(db: Session):
    strategies = (
        db.query(Strategy)
        .filter(Strategy.is_active == True, Strategy.alert_enabled == True)
        .all()
    )

    for strategy in strategies:
        try:
            _check_strategy(db, strategy)
        except Exception as e:
            logger.error(f"Strategy check failed for {strategy.name}: {e}")


def _check_strategy(db: Session, strategy: Strategy):
    conditions = json.loads(strategy.alert_conditions)
    if not conditions:
        return

    fund_id = strategy.fund_id
    if not fund_id:
        return

    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        return

    latest_price = (
        db.query(FundDailyPrice)
        .filter(FundDailyPrice.fund_id == fund_id)
        .order_by(FundDailyPrice.date.desc())
        .first()
    )
    if not latest_price:
        return

    triggered = _evaluate_conditions(conditions, latest_price)

    if triggered:
        condition_desc = json.dumps(conditions, ensure_ascii=False)
        current_values = json.dumps({
            "close": latest_price.close_price,
            "dev_30": latest_price.dev_30,
            "dev_60": latest_price.dev_60,
            "dev_90": latest_price.dev_90,
            "dev_120": latest_price.dev_120,
            "dev_180": latest_price.dev_180,
            "dev_360": latest_price.dev_360,
        }, ensure_ascii=False)

        alert = AlertLog(
            strategy_id=strategy.id,
            fund_id=fund_id,
            triggered_at=datetime.now().isoformat(),
            condition_desc=condition_desc,
            current_values=current_values,
        )
        db.add(alert)

        content = (
            f"**基金**: {fund.name} ({fund.code})\n"
            f"**策略**: {strategy.name}\n"
            f"**当前价格**: {latest_price.close_price}\n"
            f"**MA60偏差**: {latest_price.dev_60}%\n"
            f"**触发条件**: {condition_desc}"
        )
        sent = send_feishu_card_message(
            title=f"策略提醒: {fund.name}",
            content=content,
        )
        alert.notified = sent
        db.commit()


def _evaluate_conditions(conditions: list[dict], price: FundDailyPrice) -> bool:
    logic = "and"
    if isinstance(conditions, dict):
        logic = conditions.get("logic", "and")
        conditions = conditions.get("items", [])

    results = []
    for cond in conditions:
        field = cond.get("field", "dev_60")
        operator = cond.get("operator", "<")
        threshold = float(cond.get("threshold", 0))
        value = getattr(price, field, None)
        if value is None:
            results.append(False)
            continue

        if operator == "<":
            results.append(value < threshold)
        elif operator == ">":
            results.append(value > threshold)
        elif operator == "<=":
            results.append(value <= threshold)
        elif operator == ">=":
            results.append(value >= threshold)
        elif operator == "==":
            results.append(abs(value - threshold) < 0.0001)
        else:
            results.append(False)

    if logic == "or":
        return any(results)
    return all(results)
