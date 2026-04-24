"""
大盘洞察 — A股市值网格 + 指数成分叠加

100×100 网格展示全部 A 股上市公司市值分布：
- 总市值 / 10000 = 每格代表的金额
- 按市值从大到小排序，从左到右、从上到下填入网格
- 叠加沪深300、中证500、中证2000、创业板、科创板的覆盖范围

数据存入数据库，每周一刷新。API 从 DB 读取后实时计算网格。
"""

import json
import logging
import subprocess
import time
from datetime import date
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.models.fund import Fund
from app.models.fund_holding import FundHolding
from app.models.market_insight import MarketIndexComponent, MarketStock

logger = logging.getLogger(__name__)

GRID_SIZE = 100
TOTAL_CELLS = GRID_SIZE * GRID_SIZE

INDEX_MAP = {
    # 宽基指数
    "000016": "上证50",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "932000": "中证2000",
    "399006": "创业板指",
    "000688": "科创50",
    # 行业指数
    "000932": "中证消费",
    "000933": "中证医药",
    "399986": "中证银行",
    "399808": "中证新能源",
    "000993": "全指信息",
    # 红利指数
    "000922": "中证红利",
    "000015": "上证红利",
    "399324": "深证红利",
}


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _curl_get(url: str, timeout: int = 15, retries: int = 3) -> dict | list | None:
    """HTTP GET via curl (uses system CA store, works through proxy MITM)."""
    for attempt in range(retries):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", str(timeout), url],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"curl failed (attempt {attempt + 1}): {e}")
        if attempt < retries - 1:
            time.sleep(1.0 * (attempt + 1))
    return None


# ---------------------------------------------------------------------------
# Remote fetch → DB
# ---------------------------------------------------------------------------

def refresh_market_data(db: Session) -> None:
    """Fetch A-share market data + index constituents + industry from remote APIs and save to DB."""
    today = date.today()

    stocks = _fetch_all_a_shares()
    if not stocks:
        logger.error("Failed to fetch A-share data, skipping refresh")
        return

    # Fetch industry classification for all stocks
    all_codes = [s["code"] for s in stocks]
    industry_map = _fetch_stock_industries(all_codes)

    # Clear old data for today (idempotent re-run)
    db.query(MarketStock).filter(MarketStock.snapshot_date == today).delete()
    db.query(MarketIndexComponent).filter(MarketIndexComponent.snapshot_date == today).delete()

    # Save stocks
    db.bulk_save_objects([
        MarketStock(
            code=s["code"], name=s["name"],
            exchange=s["exchange"], market_cap=s["market_cap"],
            industry=industry_map.get(s["code"]),
            snapshot_date=today,
        )
        for s in stocks
    ])

    # Save index constituents
    for idx_code in INDEX_MAP:
        codes = _fetch_index_constituents(idx_code)
        db.bulk_save_objects([
            MarketIndexComponent(
                index_code=idx_code, stock_code=c, snapshot_date=today,
            )
            for c in codes
        ])

    db.commit()
    logger.info(f"Market data refreshed: {len(stocks)} stocks, {len(industry_map)} industries, snapshot_date={today}")


def _fetch_all_a_shares() -> list[dict]:
    """Fetch all A-share stocks with market cap from Sina Finance API."""
    all_stocks: list[dict] = []
    base = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

    for page in range(1, 80):
        params = urlencode({
            "page": page, "num": 100,
            "sort": "mktcap", "asc": 0,
            "node": "hs_a", "symbol": "",
            "_s_r_a": "sort",
        })
        data = _curl_get(f"{base}?{params}")
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for item in data:
            cap = item.get("mktcap")
            if cap and float(cap) > 0:
                symbol = item["symbol"]
                all_stocks.append({
                    "code": item["code"],
                    "name": item["name"],
                    "exchange": 1 if symbol.startswith("sh") else 0,
                    "market_cap": float(cap) * 10000,  # 万元 → 元
                })
        time.sleep(0.3)

    all_stocks.sort(key=lambda x: x["market_cap"], reverse=True)
    logger.info(f"Fetched {len(all_stocks)} A-shares with valid market cap")
    return all_stocks


def _fetch_stock_industries(codes: list[str]) -> dict[str, str]:
    """Fetch industry (一级行业) for stock codes from EastMoney datacenter, in batches."""
    result: dict[str, str] = {}
    base = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    batch_size = 50

    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        in_clause = ",".join(f'"{c}"' for c in batch)
        params = urlencode({
            "pageSize": batch_size, "pageNumber": 1,
            "reportName": "RPT_F10_ORG_BASICINFO",
            "columns": "SECURITY_CODE,BOARD_NAME_1LEVEL",
            "source": "WEB", "client": "WEB",
            "filter": f"(SECURITY_CODE in ({in_clause}))",
        })
        data = _curl_get(f"{base}?{params}")
        if data and isinstance(data, dict) and data.get("success"):
            for item in data.get("result", {}).get("data", []):
                code = item.get("SECURITY_CODE")
                industry = item.get("BOARD_NAME_1LEVEL")
                if code and industry:
                    result[code] = industry
        time.sleep(0.2)

    logger.info(f"Fetched industry for {len(result)}/{len(codes)} stocks")
    return result


def _fetch_index_constituents(index_code: str) -> set[str]:
    """Fetch constituent stock codes for a given index from EastMoney datacenter."""
    codes: set[str] = set()
    base = "https://datacenter-web.eastmoney.com/api/data/v1/get"

    for page in range(1, 30):
        params = urlencode({
            "pageSize": 500, "pageNumber": page,
            "reportName": "RPT_INDEX_COMPONENT",
            "columns": "SECURITY_CODE",
            "source": "WEB", "client": "WEB",
            "filter": f'(INDEX_CODE="{index_code}")',
        })
        data = _curl_get(f"{base}?{params}")
        if not data or not isinstance(data, dict) or not data.get("success"):
            break
        result = data.get("result", {})
        items = result.get("data", [])
        if not items:
            break
        for item in items:
            codes.add(item["SECURITY_CODE"])
        if len(codes) >= result.get("count", 0):
            break
        time.sleep(0.2)

    logger.info(f"Index {index_code}: {len(codes)} constituents")
    return codes


# ---------------------------------------------------------------------------
# DB → Grid (pure computation, fast)
# ---------------------------------------------------------------------------

def build_market_grid(db: Session) -> dict:
    """Build grid from the latest snapshot in DB. Returns error dict if no data."""
    # Find latest snapshot date
    latest = db.query(MarketStock.snapshot_date).order_by(
        MarketStock.snapshot_date.desc()
    ).first()
    if not latest:
        return {"error": "无数据，请先刷新大盘数据"}

    snap_date = latest[0]

    # Load stocks sorted by market cap desc
    rows = (
        db.query(MarketStock)
        .filter(MarketStock.snapshot_date == snap_date)
        .order_by(MarketStock.market_cap.desc())
        .all()
    )
    stocks = [
        {"code": r.code, "name": r.name, "market_cap": r.market_cap, "industry": r.industry or ""}
        for r in rows
    ]

    # Load index constituents
    idx_rows = (
        db.query(MarketIndexComponent)
        .filter(MarketIndexComponent.snapshot_date == snap_date)
        .all()
    )
    index_codes: dict[str, set[str]] = {code: set() for code in INDEX_MAP}
    for r in idx_rows:
        if r.index_code in index_codes:
            index_codes[r.index_code].add(r.stock_code)

    # Load fund holdings — latest quarter per active fund
    fund_codes: dict[str, set[str]] = {}  # fund_name -> set of stock codes
    fund_meta: list[dict] = []  # [{name, code, stock_count}]
    active_funds = db.query(Fund).filter(Fund.is_active.is_(True)).all()
    for fund in active_funds:
        latest_q = (
            db.query(FundHolding.quarter)
            .filter(FundHolding.fund_id == fund.id)
            .order_by(FundHolding.quarter.desc())
            .first()
        )
        if not latest_q:
            continue
        holdings = (
            db.query(FundHolding.stock_code)
            .filter(FundHolding.fund_id == fund.id, FundHolding.quarter == latest_q[0])
            .all()
        )
        stock_set = {h[0] for h in holdings}
        if stock_set:
            fund_codes[fund.name] = stock_set
            fund_meta.append({"name": fund.name, "code": fund.code, "stock_count": len(stock_set)})

    # Build grid
    total_cap = sum(s["market_cap"] for s in stocks)
    cell_value = total_cap / TOTAL_CELLS

    cells: list[dict] = []
    stock_idx = 0
    remaining_cap = 0.0
    current_stock = None
    index_cell_ranges: dict[str, dict] = {
        code: {"start_cell": -1, "end_cell": -1, "stock_count": len(codes)}
        for code, codes in index_codes.items()
    }
    fund_cell_ranges: dict[str, dict] = {
        name: {"start_cell": -1, "end_cell": -1, "stock_count": len(codes)}
        for name, codes in fund_codes.items()
    }

    for cell_num in range(TOTAL_CELLS):
        row = cell_num // GRID_SIZE
        col = cell_num % GRID_SIZE
        cell = {"row": row, "col": col, "stocks": [], "indices": []}
        budget = cell_value

        while budget > 0 and stock_idx < len(stocks):
            if remaining_cap <= 0:
                current_stock = stocks[stock_idx]
                remaining_cap = current_stock["market_cap"]

            take = min(budget, remaining_cap)
            budget -= take
            remaining_cap -= take

            if not cell["stocks"] or cell["stocks"][-1]["code"] != current_stock["code"]:
                cell["stocks"].append({
                    "code": current_stock["code"],
                    "name": current_stock["name"],
                    "market_cap": current_stock["market_cap"],
                    "industry": current_stock["industry"],
                })

            if remaining_cap <= 0:
                stock_idx += 1

        cell_stock_codes = {s["code"] for s in cell["stocks"]}
        for idx_code, idx_name in INDEX_MAP.items():
            if cell_stock_codes & index_codes.get(idx_code, set()):
                cell["indices"].append(idx_name)
                if index_cell_ranges[idx_code]["start_cell"] == -1:
                    index_cell_ranges[idx_code]["start_cell"] = cell_num
                index_cell_ranges[idx_code]["end_cell"] = cell_num

        # Overlay fund holdings
        for fund_name, fund_stock_set in fund_codes.items():
            if cell_stock_codes & fund_stock_set:
                cell["indices"].append(fund_name)
                if fund_cell_ranges[fund_name]["start_cell"] == -1:
                    fund_cell_ranges[fund_name]["start_cell"] = cell_num
                fund_cell_ranges[fund_name]["end_cell"] = cell_num

        cells.append(cell)

    # Build fund classification tree (良田模型)
    fund_classification = _build_fund_classification(db, fund_meta)

    return {
        "grid_size": GRID_SIZE,
        "total_market_cap": total_cap,
        "cell_value": cell_value,
        "stock_count": len(stocks),
        "snapshot_date": str(snap_date),
        "cells": cells,
        "index_ranges": {
            INDEX_MAP[code]: ranges
            for code, ranges in index_cell_ranges.items()
        },
        "fund_ranges": fund_cell_ranges,
        "fund_meta": fund_meta,
        "fund_classification": fund_classification,
    }


def _build_fund_classification(db: Session, fund_meta: list[dict]) -> dict | None:
    """Group fund_meta by 良田模型 classification hierarchy."""
    model = db.query(ClassModel).filter(ClassModel.name == "良田模型").first()
    if not model:
        return None

    # Load all categories for this model
    categories = db.query(ClassCategory).filter(ClassCategory.model_id == model.id).all()
    cat_by_id: dict[int, ClassCategory] = {c.id: c for c in categories}

    # Load fund -> category mappings
    mappings = db.query(FundClassMap).filter(FundClassMap.model_id == model.id).all()
    # fund_id -> category_id
    fund_cat: dict[int, int] = {m.fund_id: m.category_id for m in mappings}

    # Build fund_id -> fund_meta lookup
    fund_id_by_name: dict[str, int] = {}
    active_funds = db.query(Fund).filter(Fund.is_active.is_(True)).all()
    for f in active_funds:
        fund_id_by_name[f.name] = f.id

    # Build L1 -> L2 -> funds tree
    l1_cats = [c for c in categories if c.parent_id is None]
    l1_cats.sort(key=lambda c: c.sort_order)

    classified_fund_names: set[str] = set()
    groups = []
    for l1 in l1_cats:
        l2_cats = [c for c in categories if c.parent_id == l1.id]
        l2_cats.sort(key=lambda c: c.sort_order)

        l2_groups = []
        for l2 in l2_cats:
            # Collect all category ids under this L2 (including itself and any L3 children)
            cat_ids = {l2.id}
            for c in categories:
                if c.parent_id == l2.id:
                    cat_ids.add(c.id)

            # Find funds mapped to these categories that also have holdings
            l2_funds = []
            for fm in fund_meta:
                fid = fund_id_by_name.get(fm["name"])
                if fid and fund_cat.get(fid) in cat_ids:
                    l2_funds.append(fm)
                    classified_fund_names.add(fm["name"])

            l2_groups.append({
                "name": l2.name,
                "funds": l2_funds,
            })

        groups.append({
            "name": l1.name,
            "children": l2_groups,
        })

    # Uncategorized funds
    uncategorized = [fm for fm in fund_meta if fm["name"] not in classified_fund_names]

    return {
        "model_name": model.name,
        "groups": groups,
        "uncategorized": uncategorized,
    }
