import json
import logging
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.price import FundDailyPrice

logger = logging.getLogger(__name__)


def run_backtest(
    db: Session,
    fund_id: int,
    config: dict,
    start_date: date,
    end_date: date,
) -> dict:
    prices = (
        db.query(FundDailyPrice)
        .filter(
            FundDailyPrice.fund_id == fund_id,
            FundDailyPrice.date >= start_date,
            FundDailyPrice.date <= end_date,
        )
        .order_by(FundDailyPrice.date)
        .all()
    )

    if not prices:
        return {"error": "No price data available"}

    df = pd.DataFrame([{
        "date": p.date,
        "close": p.close_price,
        "dev_30": p.dev_30,
        "dev_60": p.dev_60,
        "dev_90": p.dev_90,
        "dev_120": p.dev_120,
        "dev_180": p.dev_180,
        "dev_360": p.dev_360,
    } for p in prices])

    buy_config = config.get("buy", {})
    sell_config = config.get("sell", {})

    cash = 0.0
    shares = 0.0
    total_invested = 0.0
    trade_log = []
    equity_curve = []

    for i, row in df.iterrows():
        buy_amount = _evaluate_buy(buy_config, row, i)
        if buy_amount > 0:
            bought_shares = buy_amount / row["close"]
            shares += bought_shares
            total_invested += buy_amount
            trade_log.append({
                "date": row["date"].isoformat(),
                "action": "buy",
                "price": round(row["close"], 4),
                "amount": round(buy_amount, 2),
                "shares": round(bought_shares, 4),
                "total_shares": round(shares, 4),
            })

        if shares > 0:
            sell_signal = _evaluate_sell(sell_config, row, shares, total_invested)
            if sell_signal:
                sell_value = shares * row["close"]
                trade_log.append({
                    "date": row["date"].isoformat(),
                    "action": "sell",
                    "price": round(row["close"], 4),
                    "amount": round(sell_value, 2),
                    "shares": round(shares, 4),
                    "total_shares": 0,
                })
                cash += sell_value
                shares = 0.0

        portfolio_value = cash + shares * row["close"]
        equity_curve.append({
            "date": row["date"].isoformat(),
            "value": round(portfolio_value, 2),
            "invested": round(total_invested, 2),
        })

    final_value = cash + shares * df.iloc[-1]["close"]
    metrics = _calculate_metrics(equity_curve, total_invested, final_value, trade_log)

    return {
        "metrics": metrics,
        "trade_log": trade_log,
        "equity_curve": equity_curve,
    }


def _evaluate_buy(config: dict, row: pd.Series, idx: int) -> float:
    buy_type = config.get("type", "dca")
    amount = config.get("amount", 1000)

    if buy_type == "dca":
        interval = config.get("interval", "weekly")
        freq = {"daily": 1, "weekly": 5, "biweekly": 10, "monthly": 20}.get(interval, 5)
        if idx % freq == 0:
            return amount
    elif buy_type == "condition":
        field = config.get("field", "dev_60")
        threshold = config.get("threshold", -5)
        val = row.get(field)
        if val is not None and val < threshold:
            return amount

    return 0.0


def _evaluate_sell(config: dict, row: pd.Series, shares: float, invested: float) -> bool:
    if not config:
        return False

    current_value = shares * row["close"]
    ret = (current_value - invested) / invested if invested > 0 else 0

    sell_type = config.get("type", "target")
    if sell_type == "target":
        target = config.get("target_return", 0.15)
        stop_loss = config.get("stop_loss", -0.10)
        if ret >= target or ret <= stop_loss:
            return True
    elif sell_type == "condition":
        field = config.get("field", "dev_60")
        threshold = config.get("threshold", 10)
        val = row.get(field)
        if val is not None and val > threshold:
            return True

    return False


def _calculate_metrics(
    equity_curve: list[dict],
    total_invested: float,
    final_value: float,
    trade_log: list[dict],
) -> dict:
    if not equity_curve or total_invested == 0:
        return {}

    total_return = (final_value - total_invested) / total_invested
    n_days = len(equity_curve)
    annual_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1 if total_return > -1 else -1

    values = pd.Series([e["value"] for e in equity_curve])
    daily_returns = values.pct_change().dropna()

    volatility = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0
    sharpe = float(annual_return / volatility) if volatility > 0 else 0

    peak = values.expanding().max()
    drawdown = (values - peak) / peak
    max_drawdown = float(drawdown.min())

    sells = [t for t in trade_log if t["action"] == "sell"]
    wins = sum(1 for s in sells if s["amount"] > 0)
    win_rate = wins / len(sells) if sells else 0

    return {
        "total_return": round(total_return, 4),
        "annual_return": round(annual_return, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(max_drawdown, 4),
        "volatility": round(volatility, 4),
        "win_rate": round(win_rate, 4),
        "profit_loss_ratio": 0,
    }
