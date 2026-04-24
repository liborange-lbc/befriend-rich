import logging
import math
from datetime import date, timedelta

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.fund_holding import FundHolding
from app.models.price import FundDailyPrice

logger = logging.getLogger(__name__)


def _get_daily_returns(db: Session, fund_id: int, start: date) -> dict[date, float]:
    """Get daily returns as {date: return} for alignment across funds."""
    rows = (
        db.query(FundDailyPrice.date, FundDailyPrice.close_price)
        .filter(FundDailyPrice.fund_id == fund_id, FundDailyPrice.date >= start)
        .order_by(asc(FundDailyPrice.date))
        .all()
    )
    prices = [(r[0], r[1]) for r in rows if r[1] and r[1] > 0]
    returns = {}
    for i in range(1, len(prices)):
        returns[prices[i][0]] = prices[i][1] / prices[i - 1][1] - 1
    return returns


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient."""
    n = len(xs)
    if n < 10:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def get_correlation_matrix(db: Session, lookback_days: int = 365) -> dict:
    """Compute pairwise return correlation matrix for active funds."""
    start = date.today() - timedelta(days=lookback_days)
    funds = db.query(Fund).filter(Fund.is_active == True).all()  # noqa: E712

    # Pre-compute returns for all funds
    fund_returns: dict[int, dict[date, float]] = {}
    fund_info: dict[int, dict] = {}
    for f in funds:
        rets = _get_daily_returns(db, f.id, start)
        if len(rets) >= 20:
            fund_returns[f.id] = rets
            fund_info[f.id] = {"fund_id": f.id, "fund_code": f.code, "fund_name": f.name}

    fund_ids = sorted(fund_returns.keys())
    labels = [fund_info[fid] for fid in fund_ids]

    # Build matrix
    n = len(fund_ids)
    matrix: list[list[float | None]] = [[None] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            ri = fund_returns[fund_ids[i]]
            rj = fund_returns[fund_ids[j]]
            common_dates = sorted(set(ri.keys()) & set(rj.keys()))
            xs = [ri[d] for d in common_dates]
            ys = [rj[d] for d in common_dates]
            corr = _pearson(xs, ys)
            matrix[i][j] = corr
            matrix[j][i] = corr

    return {"labels": labels, "matrix": matrix}


def get_holding_overlap(db: Session) -> dict:
    """Compute pairwise holding overlap (Jaccard) based on latest quarter."""
    funds = db.query(Fund).filter(Fund.is_active == True).all()  # noqa: E712

    # Get latest quarter's holdings per fund
    fund_stocks: dict[int, set[str]] = {}
    fund_info: dict[int, dict] = {}
    for f in funds:
        latest = (
            db.query(FundHolding.quarter)
            .filter(FundHolding.fund_id == f.id)
            .order_by(desc(FundHolding.quarter))
            .first()
        )
        if not latest:
            continue
        stocks = {
            h.stock_code
            for h in db.query(FundHolding)
            .filter(FundHolding.fund_id == f.id, FundHolding.quarter == latest[0])
            .all()
        }
        if stocks:
            fund_stocks[f.id] = stocks
            fund_info[f.id] = {"fund_id": f.id, "fund_code": f.code, "fund_name": f.name}

    fund_ids = sorted(fund_stocks.keys())
    labels = [fund_info[fid] for fid in fund_ids]

    n = len(fund_ids)
    matrix: list[list[float | None]] = [[None] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            si = fund_stocks[fund_ids[i]]
            sj = fund_stocks[fund_ids[j]]
            union = si | sj
            if not union:
                continue
            jaccard = len(si & sj) / len(union)
            matrix[i][j] = round(jaccard, 4)
            matrix[j][i] = round(jaccard, 4)

    return {"labels": labels, "matrix": matrix}


def get_diversification_score(db: Session, lookback_days: int = 365) -> dict:
    """Portfolio diversification score = 1 - avg pairwise correlation."""
    data = get_correlation_matrix(db, lookback_days)
    matrix = data["matrix"]
    n = len(matrix)
    if n < 2:
        return {"score": None, "avg_correlation": None, "fund_count": n}

    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] is not None:
                total += matrix[i][j]
                count += 1

    avg_corr = total / count if count > 0 else None
    score = round(1 - avg_corr, 4) if avg_corr is not None else None

    return {
        "score": score,
        "avg_correlation": round(avg_corr, 4) if avg_corr is not None else None,
        "fund_count": n,
    }
