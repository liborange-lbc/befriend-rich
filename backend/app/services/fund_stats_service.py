import logging
import math
from datetime import date, timedelta

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.price import FundDailyPrice

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.025  # 2.5% annual risk-free rate
TRADING_DAYS_PER_YEAR = 242


def _get_prices(db: Session, fund_id: int, start: date | None = None) -> list[float]:
    """Get close prices sorted by date ascending."""
    q = db.query(FundDailyPrice.close_price).filter(FundDailyPrice.fund_id == fund_id)
    if start:
        q = q.filter(FundDailyPrice.date >= start)
    rows = q.order_by(asc(FundDailyPrice.date)).all()
    return [r[0] for r in rows if r[0] and r[0] > 0]


def _daily_returns(prices: list[float]) -> list[float]:
    if len(prices) < 2:
        return []
    return [(prices[i] / prices[i - 1]) - 1 for i in range(1, len(prices))]


def _annualized_return(prices: list[float]) -> float | None:
    if len(prices) < 2:
        return None
    total_return = prices[-1] / prices[0]
    days = len(prices) - 1
    years = days / TRADING_DAYS_PER_YEAR
    if years <= 0:
        return None
    return total_return ** (1 / years) - 1


def _max_drawdown(prices: list[float]) -> float | None:
    if len(prices) < 2:
        return None
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _volatility(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    daily_vol = math.sqrt(var)
    return daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)


def _sharpe_ratio(returns: list[float]) -> float | None:
    vol = _volatility(returns)
    if vol is None or vol == 0:
        return None
    mean_daily = sum(returns) / len(returns)
    annual_return = mean_daily * TRADING_DAYS_PER_YEAR
    return (annual_return - RISK_FREE_RATE) / vol


def _period_return(prices: list[float], db: Session, fund_id: int, months: int) -> float | None:
    """Return for the last N months."""
    cutoff = date.today() - timedelta(days=months * 30)
    period_prices = _get_prices(db, fund_id, cutoff)
    if len(period_prices) < 2:
        return None
    return period_prices[-1] / period_prices[0] - 1


def compute_fund_stats(db: Session, fund_id: int) -> dict | None:
    """Compute risk/return stats for a single fund."""
    prices = _get_prices(db, fund_id)
    if len(prices) < 10:
        return None

    returns = _daily_returns(prices)

    return {
        "annualized_return": _annualized_return(prices),
        "max_drawdown": _max_drawdown(prices),
        "volatility": _volatility(returns),
        "sharpe_ratio": _sharpe_ratio(returns),
        "return_1m": _period_return(prices, db, fund_id, 1),
        "return_3m": _period_return(prices, db, fund_id, 3),
        "return_6m": _period_return(prices, db, fund_id, 6),
        "return_12m": _period_return(prices, db, fund_id, 12),
        "total_days": len(prices),
    }


def get_all_fund_stats(db: Session) -> list[dict]:
    """Compute stats for all active funds."""
    funds = db.query(Fund).filter(Fund.is_active == True).all()  # noqa: E712
    results = []
    for fund in funds:
        stats = compute_fund_stats(db, fund.id)
        if stats:
            results.append({
                "fund_id": fund.id,
                "fund_code": fund.code,
                "fund_name": fund.name,
                "currency": fund.currency,
                **stats,
            })
    return results


def get_normalized_prices(db: Session, fund_ids: list[int], start: date | None = None) -> dict:
    """Get price series normalized to 1.0 at start, for comparison charts."""
    result = {}
    for fid in fund_ids:
        q = (
            db.query(FundDailyPrice.date, FundDailyPrice.close_price)
            .filter(FundDailyPrice.fund_id == fid)
        )
        if start:
            q = q.filter(FundDailyPrice.date >= start)
        rows = q.order_by(asc(FundDailyPrice.date)).all()
        if not rows or rows[0][1] <= 0:
            continue
        base = rows[0][1]
        result[str(fid)] = [
            {"date": r[0].isoformat(), "value": round(r[1] / base, 6)}
            for r in rows if r[1] and r[1] > 0
        ]
    return result


def get_ranking_by_classification(db: Session) -> list[dict]:
    """Rank funds within each classification category."""
    from app.models.classification import ClassCategory, ClassModel, FundClassMap

    # Get the first classification model (良田模型)
    model = db.query(ClassModel).first()
    if not model:
        return []

    categories = db.query(ClassCategory).filter(ClassCategory.model_id == model.id).all()
    cat_map = {c.id: c.name for c in categories}

    mappings = db.query(FundClassMap).filter(FundClassMap.model_id == model.id).all()
    fund_to_cats: dict[int, list[int]] = {}
    for m in mappings:
        fund_to_cats.setdefault(m.fund_id, []).append(m.category_id)

    # Compute stats once
    all_stats = {s["fund_id"]: s for s in get_all_fund_stats(db)}

    groups = []
    for cat_id, cat_name in cat_map.items():
        fund_ids = [fid for fid, cats in fund_to_cats.items() if cat_id in cats]
        ranked = []
        for fid in fund_ids:
            if fid in all_stats:
                ranked.append(all_stats[fid])
        # Sort by annualized return descending
        ranked.sort(key=lambda x: x.get("annualized_return") or -999, reverse=True)
        if ranked:
            groups.append({
                "category_id": cat_id,
                "category_name": cat_name,
                "funds": ranked,
            })

    return groups
