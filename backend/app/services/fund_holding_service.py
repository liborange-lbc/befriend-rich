"""Service for fetching and querying fund constituent stock holdings."""

import logging
import re
import time
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.fund_holding import FundHolding
from app.models.portfolio import PortfolioRecord

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:  # pragma: no cover
    ak = None  # type: ignore[assignment]


def parse_quarter(raw: str) -> str:
    """Convert akshare quarter string to normalized format.

    Examples:
        "2024年4季度报告" -> "2024Q4"
        "2024年2季度报告" -> "2024Q2"
    """
    m = re.search(r"(\d{4})年(\d)季度", raw)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    return raw


# ETF联接基金 -> 母ETF 代码映射
# 联接基金季报只披露"持有XX ETF"，不披露底层股票，需用母ETF持仓代替
def _copy_holdings_from_fund(db: Session, target_fund: Fund, source_code: str) -> int:
    """Copy holdings from another fund in the DB (for FOF funds)."""
    source = db.query(Fund).filter(Fund.code == source_code).first()
    if not source:
        logger.warning(f"Source fund {source_code} not found for copy")
        return 0
    source_holdings = get_fund_holdings(db, source.id)
    if not source_holdings:
        logger.info(f"Source fund {source_code} has no holdings to copy")
        return 0

    count = 0
    for h in source_holdings:
        existing = (
            db.query(FundHolding)
            .filter(
                FundHolding.fund_id == target_fund.id,
                FundHolding.quarter == h.quarter,
                FundHolding.stock_code == h.stock_code,
            )
            .first()
        )
        if existing:
            existing.stock_name = h.stock_name
            existing.holding_ratio = h.holding_ratio
            existing.holding_shares = h.holding_shares
            existing.holding_value = h.holding_value
            existing.disclosure_date = h.disclosure_date
        else:
            db.add(FundHolding(
                fund_id=target_fund.id,
                quarter=h.quarter,
                stock_code=h.stock_code,
                stock_name=h.stock_name,
                holding_ratio=h.holding_ratio,
                holding_shares=h.holding_shares,
                holding_value=h.holding_value,
                disclosure_date=h.disclosure_date,
            ))
        count += 1
    db.commit()
    logger.info(f"Copied {count} holdings from {source_code} to {target_fund.code}")
    return count


def _try_fetch_holdings(symbol: str, year_str: str):
    """Try to fetch holdings DataFrame, returning None on failure."""
    try:
        df = ak.fund_portfolio_hold_em(symbol=symbol, date=year_str)
        return df
    except Exception as e:
        logger.warning(f"Failed to fetch holdings for {symbol} ({year_str}): {e}")
        return None


# ETF联接基金 -> 母ETF 代码映射
# 联接基金季报只披露"持有XX ETF"，不披露底层股票，需用母ETF持仓代替


def fetch_holdings_for_fund(db: Session, fund: Fund, year: int | None = None) -> int:
    """Fetch holdings for a single fund from akshare and upsert into DB.

    For ETF联接 funds, fetches the underlying ETF's holdings instead.
    Returns count of rows upserted.
    """
    if ak is None:
        logger.error("akshare not installed")
        return 0

    pure_code = fund.code.split(".")[0]
    year_str = str(year) if year else str(date.today().year)

    # Try direct fetch first
    df = _try_fetch_holdings(pure_code, year_str)

    # Fallback: use holding_source from fund record
    if (df is None or df.empty) and fund.holding_source:
        source_code = fund.holding_source
        # Try akshare with the source code first
        logger.info(f"Trying holding_source {source_code} for {fund.code}")
        df = _try_fetch_holdings(source_code, year_str)
        # If akshare also fails, try copying from DB fund
        if (df is None or df.empty):
            source_fund = db.query(Fund).filter(Fund.code == source_code).first()
            if source_fund:
                logger.info(f"Copying holdings from fund {source_code} for {fund.code}")
                return _copy_holdings_from_fund(db, fund, source_code)

    if df is None or df.empty:
        logger.info(f"No holdings data for {fund.code} ({year_str})")
        return 0

    count = 0
    for _, row in df.iterrows():
        raw_quarter = str(row.get("季度", ""))
        quarter = parse_quarter(raw_quarter)
        stock_code = str(row.get("股票代码", ""))
        stock_name = str(row.get("股票名称", ""))

        if not stock_code or not quarter:
            continue

        holding_ratio = _safe_float(row.get("占净值比例"))
        holding_shares = _safe_float(row.get("持股数") or row.get("持仓股数"))
        holding_value = _safe_float(row.get("持仓市值"))

        existing = (
            db.query(FundHolding)
            .filter(
                FundHolding.fund_id == fund.id,
                FundHolding.quarter == quarter,
                FundHolding.stock_code == stock_code,
            )
            .first()
        )

        if existing:
            existing.stock_name = stock_name
            existing.holding_ratio = holding_ratio
            existing.holding_shares = holding_shares
            existing.holding_value = holding_value
            existing.disclosure_date = raw_quarter
        else:
            db.add(FundHolding(
                fund_id=fund.id,
                quarter=quarter,
                stock_code=stock_code,
                stock_name=stock_name,
                holding_ratio=holding_ratio,
                holding_shares=holding_shares,
                holding_value=holding_value,
                disclosure_date=raw_quarter,
            ))
        count += 1

    db.commit()
    logger.info(f"Upserted {count} holdings for {fund.code} ({year_str})")
    return count


def fetch_holdings_for_all_funds(db: Session) -> dict[str, int]:
    """Fetch holdings for all active funds. Returns {fund_code: count}."""
    funds = db.query(Fund).filter(Fund.is_active.is_(True)).all()
    result: dict[str, int] = {}
    current_year = date.today().year

    for fund in funds:
        n = fetch_holdings_for_fund(db, fund, current_year)
        # In Q1, also fetch previous year to catch late Q4 disclosures
        if date.today().month <= 3:
            n += fetch_holdings_for_fund(db, fund, current_year - 1)
        result[fund.code] = n
        time.sleep(0.5)  # Rate limiting

    return result


def get_fund_holdings(
    db: Session, fund_id: int, quarter: str | None = None
) -> list[FundHolding]:
    """Get holdings for a fund. Returns latest quarter if quarter is None."""
    query = db.query(FundHolding).filter(FundHolding.fund_id == fund_id)

    if quarter:
        query = query.filter(FundHolding.quarter == quarter)
    else:
        # Find latest quarter
        latest = (
            db.query(FundHolding.quarter)
            .filter(FundHolding.fund_id == fund_id)
            .order_by(FundHolding.quarter.desc())
            .first()
        )
        if not latest:
            return []
        query = query.filter(FundHolding.quarter == latest[0])

    return query.order_by(FundHolding.holding_ratio.desc().nullslast()).all()


def get_fund_positions(db: Session) -> dict[int, float]:
    """Get latest portfolio position (amount_cny) per fund_id."""
    latest_date = (
        db.query(PortfolioRecord.record_date)
        .order_by(PortfolioRecord.record_date.desc())
        .first()
    )
    if not latest_date:
        return {}
    records = (
        db.query(PortfolioRecord)
        .filter(PortfolioRecord.record_date == latest_date[0])
        .all()
    )
    positions: dict[int, float] = defaultdict(float)
    for r in records:
        positions[r.fund_id] += r.amount_cny
    return dict(positions)


def get_available_quarters(db: Session, fund_id: int | None = None) -> list[str]:
    """Get distinct quarters, optionally for a specific fund."""
    query = db.query(FundHolding.quarter).distinct()
    if fund_id:
        query = query.filter(FundHolding.fund_id == fund_id)
    rows = query.order_by(FundHolding.quarter.desc()).all()
    return [r[0] for r in rows]


def get_stock_exposure(db: Session, target_date: date | None = None) -> list[dict]:
    """Calculate actual stock exposure based on latest holdings x portfolio positions.

    For each fund with a portfolio position, multiply amount_cny * (holding_ratio / 100)
    to get actual stock exposure. Aggregate across funds.
    """
    # Get latest portfolio positions
    if target_date:
        records = (
            db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == target_date)
            .all()
        )
    else:
        # Find latest record date
        latest_date = (
            db.query(PortfolioRecord.record_date)
            .order_by(PortfolioRecord.record_date.desc())
            .first()
        )
        if not latest_date:
            return []
        records = (
            db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == latest_date[0])
            .all()
        )

    # Aggregate positions per fund_id
    fund_positions: dict[int, float] = defaultdict(float)
    for r in records:
        fund_positions[r.fund_id] += r.amount_cny

    if not fund_positions:
        return []

    # For each fund, get latest holdings and compute exposure
    stock_map: dict[str, dict] = {}  # stock_code -> aggregated info

    for fund_id, amount_cny in fund_positions.items():
        fund = db.query(Fund).filter(Fund.id == fund_id).first()
        if not fund:
            continue

        holdings = get_fund_holdings(db, fund_id)
        for h in holdings:
            if h.holding_ratio is None:
                continue

            exposure_cny = amount_cny * h.holding_ratio / 100.0

            if h.stock_code not in stock_map:
                stock_map[h.stock_code] = {
                    "stock_code": h.stock_code,
                    "stock_name": h.stock_name,
                    "total_exposure_cny": 0.0,
                    "funds": [],
                }

            stock_map[h.stock_code]["total_exposure_cny"] += exposure_cny
            stock_map[h.stock_code]["funds"].append({
                "fund_id": fund_id,
                "fund_name": fund.name,
                "amount_cny": amount_cny,
                "holding_ratio": h.holding_ratio,
                "exposure_cny": round(exposure_cny, 2),
            })

    result = sorted(stock_map.values(), key=lambda x: x["total_exposure_cny"], reverse=True)
    for item in result:
        item["total_exposure_cny"] = round(item["total_exposure_cny"], 2)

    return result


def get_aggregated_holdings(db: Session, fund_ids: list[int]) -> list[dict]:
    """Aggregate latest-quarter holdings across multiple funds.

    Groups by stock_code, sums holding_value, collects per-fund breakdown.
    """
    positions = get_fund_positions(db)
    stock_map: dict[str, dict] = {}

    for fid in fund_ids:
        fund = db.query(Fund).filter(Fund.id == fid).first()
        if not fund:
            continue
        pos = positions.get(fid, 0.0)
        holdings = get_fund_holdings(db, fid)
        for h in holdings:
            key = h.stock_code
            if key not in stock_map:
                stock_map[key] = {
                    "stock_code": h.stock_code,
                    "stock_name": h.stock_name,
                    "total_holding_value": 0.0,
                    "total_holding_ratio": 0.0,
                    "total_holding_amount": 0.0,
                    "fund_count": 0,
                    "funds": [],
                }
            entry = stock_map[key]
            val = h.holding_value or 0.0
            ratio = h.holding_ratio or 0.0
            amount = round(pos * ratio / 100, 2) if pos and ratio else 0.0
            entry["total_holding_value"] += val
            entry["total_holding_ratio"] += ratio
            entry["total_holding_amount"] += amount
            entry["fund_count"] += 1
            entry["funds"].append({
                "fund_id": fid,
                "fund_name": fund.name,
                "fund_code": fund.code,
                "holding_ratio": h.holding_ratio,
                "holding_value": h.holding_value,
                "holding_amount": amount,
                "quarter": h.quarter,
            })

    result = sorted(stock_map.values(), key=lambda x: x["total_holding_amount"], reverse=True)
    for item in result:
        item["total_holding_value"] = round(item["total_holding_value"], 2)
        item["total_holding_ratio"] = round(item["total_holding_ratio"], 2)
        item["total_holding_amount"] = round(item["total_holding_amount"], 2)
    return result


def _safe_float(val) -> float | None:
    """Safely convert a value to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
