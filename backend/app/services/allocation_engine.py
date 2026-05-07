"""良田模型 dynamic allocation engine.

Calculates optimal portfolio weights across L2 categories using
mean-variance optimization (with numpy) or risk-parity fallback.
"""

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.allocation import AllocationSnapshot, AllocationTarget
from app.models.classification import ClassCategory, FundClassMap
from app.models.portfolio import PortfolioRecord
from app.models.price import FundDailyPrice

logger = logging.getLogger(__name__)

TARGET_RETURN = 0.10
RISK_FREE_RATE = 0.02
BACKTEST_YEARS = 5
MAX_WEIGHT = 0.30
TRADING_DAYS = 252

# Exponential decay weights for years [-5, -4, -3, -2, -1]
YEAR_WEIGHTS = [0.10, 0.15, 0.20, 0.25, 0.30]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _get_l2_categories(db: Session, model_id: int) -> list[ClassCategory]:
    """Load all L2 categories for the model."""
    return (
        db.query(ClassCategory)
        .filter(ClassCategory.model_id == model_id, ClassCategory.level == 2)
        .order_by(ClassCategory.sort_order)
        .all()
    )


def _get_parent_name(db: Session, category: ClassCategory) -> str:
    """Get L1 parent name for a L2 category."""
    if category.parent_id is None:
        return ""
    parent = db.query(ClassCategory).filter(ClassCategory.id == category.parent_id).first()
    return parent.name if parent else ""


def _get_fund_ids_for_category(db: Session, category_id: int, model_id: int) -> list[int]:
    """Get fund_ids mapped to a category."""
    rows = (
        db.query(FundClassMap.fund_id)
        .filter(FundClassMap.category_id == category_id, FundClassMap.model_id == model_id)
        .all()
    )
    return [r.fund_id for r in rows]


def _get_daily_prices(
    db: Session, fund_id: int, start_date: datetime,
) -> list[tuple[datetime, float]]:
    """Get daily (date, close_price) sorted ascending."""
    rows = (
        db.query(FundDailyPrice.date, FundDailyPrice.close_price)
        .filter(FundDailyPrice.fund_id == fund_id, FundDailyPrice.date >= start_date.date())
        .order_by(FundDailyPrice.date)
        .all()
    )
    return [(r.date, r.close_price) for r in rows]


def _get_latest_holdings(db: Session) -> dict[int, float]:
    """Get latest holding amount_cny per fund_id from PortfolioRecord."""
    subq = (
        db.query(
            PortfolioRecord.fund_id,
            func.max(PortfolioRecord.record_date).label("max_date"),
        )
        .group_by(PortfolioRecord.fund_id)
        .subquery()
    )
    rows = (
        db.query(PortfolioRecord.fund_id, PortfolioRecord.amount_cny)
        .join(
            subq,
            (PortfolioRecord.fund_id == subq.c.fund_id)
            & (PortfolioRecord.record_date == subq.c.max_date),
        )
        .all()
    )
    # Sum across channels for the same fund
    holdings: dict[int, float] = defaultdict(float)
    for r in rows:
        holdings[r.fund_id] += r.amount_cny
    return dict(holdings)


def _compute_daily_returns(prices: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """Compute daily returns from price series."""
    if len(prices) < 2:
        return []
    returns = []
    for i in range(1, len(prices)):
        prev_close = prices[i - 1][1]
        if prev_close == 0:
            continue
        ret = (prices[i][1] / prev_close) - 1.0
        returns.append((prices[i][0], ret))
    return returns


def _apply_exponential_decay(
    returns: list[tuple[datetime, float]], now: datetime,
) -> list[tuple[datetime, float]]:
    """Apply exponential decay weighting: recent years weigh more."""
    if not returns:
        return returns

    weighted = []
    for dt, ret in returns:
        # Years ago (0 = current year)
        if hasattr(dt, "year"):
            years_ago = now.year - dt.year
        else:
            years_ago = 0
        # Map to weight index: 0 years ago -> index 4, 4 years ago -> index 0
        idx = max(0, min(len(YEAR_WEIGHTS) - 1, len(YEAR_WEIGHTS) - 1 - years_ago))
        weight = YEAR_WEIGHTS[idx]
        weighted.append((dt, ret * weight / YEAR_WEIGHTS[-1]))  # Normalize so recent=1.0
    return weighted


def _build_category_return_series(
    db: Session,
    fund_ids: list[int],
    holdings: dict[int, float],
    start_date: datetime,
) -> dict[datetime, float]:
    """Build weighted daily return series for a category.

    Weight by holding amount; equal-weight if no holdings.
    """
    if not fund_ids:
        return {}

    # Collect per-fund returns
    fund_returns: dict[int, dict] = {}
    for fid in fund_ids:
        prices = _get_daily_prices(db, fid, start_date)
        rets = _compute_daily_returns(prices)
        if rets:
            fund_returns[fid] = {dt: r for dt, r in rets}

    if not fund_returns:
        return {}

    # Determine weights
    total_holding = sum(holdings.get(fid, 0) for fid in fund_returns)
    if total_holding > 0:
        weights = {fid: holdings.get(fid, 0) / total_holding for fid in fund_returns}
    else:
        eq = 1.0 / len(fund_returns)
        weights = {fid: eq for fid in fund_returns}

    # Merge all dates
    all_dates: set = set()
    for dr in fund_returns.values():
        all_dates.update(dr.keys())

    # Weighted return per date
    series: dict[datetime, float] = {}
    for dt in sorted(all_dates):
        weighted_ret = 0.0
        weight_sum = 0.0
        for fid, dr in fund_returns.items():
            if dt in dr:
                weighted_ret += dr[dt] * weights[fid]
                weight_sum += weights[fid]
        if weight_sum > 0:
            series[dt] = weighted_ret / weight_sum * weight_sum  # Already weighted
    return series


def _calc_metrics(returns: list[float]) -> dict:
    """Calculate annualized return, volatility, max drawdown, sharpe."""
    if len(returns) < 20:
        return {
            "annual_return": 0.0,
            "volatility": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }

    arr = np.array(returns)
    mean_daily = float(np.mean(arr))
    std_daily = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0

    annual_return = mean_daily * TRADING_DAYS
    volatility = std_daily * math.sqrt(TRADING_DAYS)

    # Max drawdown from cumulative returns
    cumulative = np.cumprod(1.0 + arr)
    peak = np.maximum.accumulate(cumulative)
    drawdowns = (peak - cumulative) / peak
    max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    sharpe = (annual_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0.0

    return {
        "annual_return": round(annual_return, 6),
        "volatility": round(volatility, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
    }


def _risk_parity_weights(cov_matrix: np.ndarray, n: int) -> np.ndarray:
    """Simple risk-parity: weight inversely proportional to volatility.

    Used as fallback when scipy is not available.
    """
    vols = np.sqrt(np.diag(cov_matrix))
    # Replace zeros with a large number to get near-zero weight
    vols = np.where(vols > 0, vols, 1e6)
    inv_vols = 1.0 / vols
    weights = inv_vols / np.sum(inv_vols)
    # Clip to MAX_WEIGHT
    weights = np.minimum(weights, MAX_WEIGHT)
    # Renormalize
    weights = weights / np.sum(weights)
    return weights


def _mean_variance_optimize(
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n: int,
) -> np.ndarray:
    """Mean-variance optimization using scipy if available, else risk-parity."""
    try:
        from scipy.optimize import minimize

        def portfolio_variance(w: np.ndarray) -> float:
            return float(w @ cov_matrix @ w)

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "ineq", "fun": lambda w: w @ expected_returns - TARGET_RETURN},
        ]
        bounds = [(0.0, MAX_WEIGHT) for _ in range(n)]
        x0 = np.ones(n) / n

        result = minimize(
            portfolio_variance,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-12},
        )

        if result.success:
            weights = result.x
            weights = np.maximum(weights, 0.0)
            weights = weights / np.sum(weights)
            return weights

        logger.warning("MVO did not converge: %s. Trying without return constraint.", result.message)

        # Retry without target return constraint (minimum variance only)
        constraints_relaxed = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        ]
        result2 = minimize(
            portfolio_variance,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints_relaxed,
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        if result2.success:
            weights = result2.x
            weights = np.maximum(weights, 0.0)
            weights = weights / np.sum(weights)
            return weights

    except ImportError:
        logger.info("scipy not available, using risk-parity fallback")
    except Exception as e:
        logger.warning("MVO failed: %s. Falling back to risk-parity.", e)

    return _risk_parity_weights(cov_matrix, n)


def calculate_optimal_allocation(
    db: Session,
    model_id: int = 1,
    trigger: str = "manual",
) -> dict:
    """Core allocation calculation.

    Returns dict with keys: targets, snapshot, portfolio_metrics.
    """
    now = datetime.now()
    now_iso = now.isoformat(timespec="seconds")
    start_date = now - timedelta(days=BACKTEST_YEARS * 365)

    # Step 1: Load L2 categories
    categories = _get_l2_categories(db, model_id)
    if not categories:
        return {"error": "No L2 categories found for model", "targets": [], "snapshot": None}

    # Build parent name lookup
    cat_parent_names: dict[int, str] = {}
    for cat in categories:
        cat_parent_names[cat.id] = _get_parent_name(db, cat)

    # Step 2: Build daily return series per category
    holdings = _get_latest_holdings(db)
    category_series: dict[int, dict] = {}
    category_fund_ids: dict[int, list[int]] = {}

    for cat in categories:
        fund_ids = _get_fund_ids_for_category(db, cat.id, model_id)
        category_fund_ids[cat.id] = fund_ids
        if not fund_ids:
            logger.warning("Category %s (%s) has no funds mapped", cat.id, cat.name)
            category_series[cat.id] = {}
            continue
        series = _build_category_return_series(db, fund_ids, holdings, start_date)
        category_series[cat.id] = series

    # Step 3: Align dates across all categories for correlation/covariance
    all_dates: set = set()
    for s in category_series.values():
        all_dates.update(s.keys())
    sorted_dates = sorted(all_dates)

    n = len(categories)
    cat_ids = [c.id for c in categories]

    # Build return matrix (dates x categories)
    # For categories with no data, fill with 0 return (no contribution)
    returns_matrix: list[list[float]] = []
    for dt in sorted_dates:
        row = []
        for cid in cat_ids:
            row.append(category_series.get(cid, {}).get(dt, 0.0))
        returns_matrix.append(row)

    # Apply exponential decay weighting
    if returns_matrix:
        arr = np.array(returns_matrix)
        # Build weight vector per row based on position (older=lower weight)
        total_rows = len(returns_matrix)
        decay_weights = np.array([
            YEAR_WEIGHTS[max(0, min(len(YEAR_WEIGHTS) - 1, int(i / total_rows * len(YEAR_WEIGHTS))))]
            for i in range(total_rows)
        ])
        decay_weights = decay_weights / decay_weights.mean()  # Normalize to preserve scale
        weighted_arr = arr * decay_weights[:, np.newaxis]
    else:
        arr = np.zeros((0, n))
        weighted_arr = arr

    # Step 3b: Per-category metrics
    category_metrics: dict[int, dict] = {}
    for i, cid in enumerate(cat_ids):
        if weighted_arr.shape[0] > 0:
            col = weighted_arr[:, i].tolist()
        else:
            col = []
        category_metrics[cid] = _calc_metrics(col)

    # Step 4: Covariance and correlation matrices
    if weighted_arr.shape[0] > n:
        cov_matrix = np.cov(weighted_arr, rowvar=False) * TRADING_DAYS
        corr_matrix = np.corrcoef(weighted_arr, rowvar=False)
    else:
        logger.warning("Insufficient data for covariance (%d rows, %d categories)", weighted_arr.shape[0], n)
        cov_matrix = np.eye(n) * 0.04  # Assume 20% vol each
        corr_matrix = np.eye(n)

    # Step 5: Mean-variance optimization
    expected_returns = np.array([category_metrics[cid]["annual_return"] for cid in cat_ids])
    optimal_weights = _mean_variance_optimize(expected_returns, cov_matrix, n)

    # Portfolio-level metrics
    port_return = float(optimal_weights @ expected_returns)
    port_var = float(optimal_weights @ cov_matrix @ optimal_weights)
    port_vol = math.sqrt(max(port_var, 0))
    port_sharpe = (port_return - RISK_FREE_RATE) / port_vol if port_vol > 0 else 0.0

    # Step 6: Current actual weights
    total_capital = 0.0
    category_holdings: dict[int, float] = defaultdict(float)
    for cat in categories:
        for fid in category_fund_ids.get(cat.id, []):
            amt = holdings.get(fid, 0.0)
            category_holdings[cat.id] += amt
            total_capital += amt

    current_weights: dict[int, float] = {}
    for cid in cat_ids:
        current_weights[cid] = category_holdings[cid] / total_capital if total_capital > 0 else 0.0

    # Step 7: Save results
    # Deactivate previous targets
    db.query(AllocationTarget).filter(
        AllocationTarget.model_id == model_id,
        AllocationTarget.status == "active",
    ).update({"status": "replaced"})

    targets_data = []
    for i, cat in enumerate(categories):
        cid = cat.id
        tw = round(float(optimal_weights[i]), 6)
        cw = round(current_weights.get(cid, 0.0), 6)
        dev = round(tw - cw, 6)
        metrics = category_metrics.get(cid, {})

        target = AllocationTarget(
            model_id=model_id,
            category_id=cid,
            category_name=cat.name,
            parent_name=cat_parent_names.get(cid, ""),
            target_weight=tw,
            current_weight=cw,
            deviation=dev,
            annual_return=metrics.get("annual_return"),
            volatility=metrics.get("volatility"),
            max_drawdown=metrics.get("max_drawdown"),
            sharpe_ratio=metrics.get("sharpe_ratio"),
            calculated_at=now_iso,
            status="active",
        )
        db.add(target)
        targets_data.append({
            "category_id": cid,
            "category_name": cat.name,
            "parent_name": cat_parent_names.get(cid, ""),
            "target_weight": tw,
            "current_weight": cw,
            "deviation": dev,
            **metrics,
        })

    # Build weights snapshot
    weights_snapshot = [
        {"category_id": cat_ids[i], "weight": round(float(optimal_weights[i]), 6)}
        for i in range(n)
    ]

    # Correlation matrix as nested list
    corr_list = corr_matrix.tolist() if isinstance(corr_matrix, np.ndarray) else []

    # Reasoning text
    top_allocs = sorted(targets_data, key=lambda x: x["target_weight"], reverse=True)[:3]
    reasoning_parts = [
        f"基于{BACKTEST_YEARS}年历史数据的均值-方差优化结果。",
        f"组合预期年化收益: {port_return:.2%}, 波动率: {port_vol:.2%}, 夏普比率: {port_sharpe:.2f}。",
        "权重最高的三个类别: " + ", ".join(
            f"{t['category_name']}({t['target_weight']:.1%})" for t in top_allocs
        ) + "。",
    ]
    reasoning = " ".join(reasoning_parts)

    snapshot = AllocationSnapshot(
        model_id=model_id,
        trigger=trigger,
        total_capital=round(total_capital, 2),
        target_return=TARGET_RETURN,
        risk_free_rate=RISK_FREE_RATE,
        backtest_years=BACKTEST_YEARS,
        weights_snapshot=json.dumps(weights_snapshot, ensure_ascii=False),
        correlation_matrix=json.dumps(corr_list),
        portfolio_expected_return=round(port_return, 6),
        portfolio_volatility=round(port_vol, 6),
        portfolio_sharpe=round(port_sharpe, 4),
        reasoning=reasoning,
        created_at=now_iso,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return {
        "targets": targets_data,
        "snapshot": {
            "id": snapshot.id,
            "trigger": snapshot.trigger,
            "total_capital": snapshot.total_capital,
            "portfolio_expected_return": snapshot.portfolio_expected_return,
            "portfolio_volatility": snapshot.portfolio_volatility,
            "portfolio_sharpe": snapshot.portfolio_sharpe,
            "reasoning": snapshot.reasoning,
            "created_at": snapshot.created_at,
        },
        "portfolio_metrics": {
            "expected_return": round(port_return, 6),
            "volatility": round(port_vol, 6),
            "sharpe_ratio": round(port_sharpe, 4),
        },
    }


def get_current_allocation(db: Session, model_id: int = 1) -> list[dict]:
    """Return current active allocation targets."""
    targets = (
        db.query(AllocationTarget)
        .filter(AllocationTarget.model_id == model_id, AllocationTarget.status == "active")
        .order_by(AllocationTarget.id)
        .all()
    )
    return [
        {
            "id": t.id,
            "category_id": t.category_id,
            "category_name": t.category_name,
            "parent_name": t.parent_name,
            "target_weight": t.target_weight,
            "current_weight": t.current_weight,
            "deviation": t.deviation,
            "annual_return": t.annual_return,
            "volatility": t.volatility,
            "max_drawdown": t.max_drawdown,
            "sharpe_ratio": t.sharpe_ratio,
            "calculated_at": t.calculated_at,
        }
        for t in targets
    ]


def get_allocation_history(
    db: Session, model_id: int = 1, limit: int = 10, offset: int = 0,
) -> tuple[list[dict], int]:
    """Return past allocation snapshots (paginated)."""
    q = db.query(AllocationSnapshot).filter(AllocationSnapshot.model_id == model_id)
    total = q.count()
    snapshots = (
        q.order_by(desc(AllocationSnapshot.id))
        .offset(offset)
        .limit(limit)
        .all()
    )
    data = [
        {
            "id": s.id,
            "trigger": s.trigger,
            "total_capital": s.total_capital,
            "target_return": s.target_return,
            "risk_free_rate": s.risk_free_rate,
            "backtest_years": s.backtest_years,
            "weights_snapshot": json.loads(s.weights_snapshot) if s.weights_snapshot else [],
            "portfolio_expected_return": s.portfolio_expected_return,
            "portfolio_volatility": s.portfolio_volatility,
            "portfolio_sharpe": s.portfolio_sharpe,
            "reasoning": s.reasoning,
            "created_at": s.created_at,
        }
        for s in snapshots
    ]
    return data, total


def get_deviation_summary(db: Session, model_id: int = 1) -> dict:
    """Return current deviations with rebalance suggestions."""
    targets = (
        db.query(AllocationTarget)
        .filter(AllocationTarget.model_id == model_id, AllocationTarget.status == "active")
        .order_by(AllocationTarget.id)
        .all()
    )
    if not targets:
        return {"deviations": [], "needs_rebalance": False, "suggestions": []}

    # Get total capital from holdings
    holdings = _get_latest_holdings(db)
    total_capital = sum(holdings.values())

    deviations = []
    suggestions = []
    max_abs_dev = 0.0

    for t in targets:
        abs_dev = abs(t.deviation)
        max_abs_dev = max(max_abs_dev, abs_dev)

        entry = {
            "category_id": t.category_id,
            "category_name": t.category_name,
            "parent_name": t.parent_name,
            "target_weight": t.target_weight,
            "current_weight": t.current_weight,
            "deviation": t.deviation,
            "deviation_pct": round(abs_dev * 100, 2),
        }

        if total_capital > 0:
            amount_diff = round(t.deviation * total_capital, 2)
            entry["amount_diff_cny"] = amount_diff
        else:
            entry["amount_diff_cny"] = 0.0

        deviations.append(entry)

        # Suggest rebalance if deviation > 5%
        if abs_dev > 0.05:
            action = "增配" if t.deviation > 0 else "减配"
            suggestions.append({
                "category_name": t.category_name,
                "action": action,
                "deviation": round(t.deviation, 4),
                "amount_cny": round(abs(entry["amount_diff_cny"]), 2),
                "priority": "high" if abs_dev > 0.10 else "medium",
            })

    needs_rebalance = max_abs_dev > 0.05

    # Sort suggestions by priority
    priority_order = {"high": 0, "medium": 1}
    suggestions.sort(key=lambda s: priority_order.get(s["priority"], 2))

    return {
        "deviations": deviations,
        "needs_rebalance": needs_rebalance,
        "max_deviation_pct": round(max_abs_dev * 100, 2),
        "total_capital": round(total_capital, 2),
        "suggestions": suggestions,
    }
