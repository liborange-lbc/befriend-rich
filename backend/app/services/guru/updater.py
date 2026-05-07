"""价值大师持仓数据更新服务。

整合天天基金（中国公募）和 SEC EDGAR（海外 13F）两个官方数据源，
每月更新 guru 持仓数据。
"""

import logging
import re

from sqlalchemy.orm import Session

from app.models.guru import Guru, GuruHolding, GuruStock

from .eastmoney import CHINA_FUND_CODES, fetch_all_china_funds
from .sec_edgar import GURU_CIK_MAP, fetch_all_13f_gurus

logger = logging.getLogger(__name__)


def _detect_market(code: str) -> str:
    if code.startswith("TPE:"):
        return "TW"
    if code.startswith("HKG:") or code.endswith(".HK"):
        return "HK"
    if re.match(r"^\d{6}$", code):
        return "A"
    return "US"


def _update_guru_holdings(
    db: Session,
    slug: str,
    holdings: list[dict],
    stock_tracker: dict[str, set],
) -> int:
    """更新单个 guru 的持仓数据。

    Returns:
        更新的持仓数量
    """
    guru = db.query(Guru).filter(Guru.slug == slug).first()
    if not guru:
        logger.warning(f"Guru {slug} not found in DB, skipping")
        return 0

    # 删除旧持仓
    db.query(GuruHolding).filter(GuruHolding.guru_id == guru.id).delete()

    # 插入新持仓
    count = 0
    for h in holdings:
        code = h.get("stock_code", "")
        name = h.get("stock_name", "")
        if not code and not name:
            continue

        db.add(GuruHolding(
            guru_id=guru.id,
            stock_code=code,
            stock_name=name,
            weight_pct=h.get("weight_pct", ""),
            shares=h.get("shares", ""),
            value=h.get("value", ""),
            # These fields may not be available from official sources
            position_change="",
            trade_impact_pct="",
            ownership_pct="",
            sector=h.get("sector", ""),
            market_cap="",
            return_3m_pct="",
            return_ytd_pct="",
        ))
        count += 1

        # Track for stock aggregation
        if code:
            if code not in stock_tracker:
                stock_tracker[code] = {"name": name, "slugs": set()}
            stock_tracker[code]["slugs"].add(slug)

    # 更新 guru 持仓数
    guru.num_holdings = count
    db.flush()

    return count


def _rebuild_stock_index(db: Session, stock_tracker: dict[str, set]) -> int:
    """重建 guru_stocks 聚合索引表。"""
    # 先获取现有数据保留 sector 信息
    existing = {s.code: s.sector for s in db.query(GuruStock).all()}

    db.query(GuruStock).delete()

    count = 0
    for code, info in stock_tracker.items():
        db.add(GuruStock(
            code=code,
            name=info["name"],
            market=_detect_market(code),
            sector=existing.get(code, ""),
            guru_count=len(info["slugs"]),
        ))
        count += 1

    db.flush()
    return count


def update_all_guru_holdings(db: Session) -> dict:
    """从官方披露网站获取并更新所有 guru 持仓数据。

    数据源：
    - 中国公募基金：天天基金网（eastmoney.com）— 季度持仓披露
    - 海外机构投资者：SEC EDGAR 13F 文件 — 季度持仓披露

    Returns:
        dict with update summary
    """
    logger.info("Starting guru holdings update from official sources")

    # 1) 获取中国公募基金持仓
    logger.info(f"Fetching {len(CHINA_FUND_CODES)} Chinese fund holdings from eastmoney...")
    china_results = fetch_all_china_funds(delay=0.5)

    # 2) 获取 13F 持仓
    logger.info(f"Fetching {len(GURU_CIK_MAP)} institutional 13F holdings from SEC EDGAR...")
    sec_results = fetch_all_13f_gurus(delay=1.0)

    # 3) 更新数据库
    stock_tracker: dict[str, set] = {}  # code → {name, slugs}
    updated_gurus = 0
    total_holdings = 0

    # 也收集未更新的 guru 的持仓到 stock_tracker（保持 stock 索引完整）
    all_slugs = set()
    for slug in list(china_results.keys()) + list(sec_results.keys()):
        all_slugs.add(slug)

    # 收集旧数据中未被更新的 guru 持仓
    untouched_gurus = (
        db.query(Guru)
        .filter(Guru.slug.notin_(list(all_slugs)))
        .all()
    )
    for guru in untouched_gurus:
        for h in db.query(GuruHolding).filter(GuruHolding.guru_id == guru.id).all():
            if h.stock_code:
                if h.stock_code not in stock_tracker:
                    stock_tracker[h.stock_code] = {"name": h.stock_name or "", "slugs": set()}
                stock_tracker[h.stock_code]["slugs"].add(guru.slug)

    # 更新中国基金
    for slug, holdings in china_results.items():
        count = _update_guru_holdings(db, slug, holdings, stock_tracker)
        if count > 0:
            updated_gurus += 1
            total_holdings += count
            logger.info(f"  {slug}: {count} holdings updated (eastmoney)")

    # 更新 13F 机构
    for slug, holdings in sec_results.items():
        count = _update_guru_holdings(db, slug, holdings, stock_tracker)
        if count > 0:
            updated_gurus += 1
            total_holdings += count
            logger.info(f"  {slug}: {count} holdings updated (SEC EDGAR)")

    # 4) 重建 stock 索引
    stock_count = _rebuild_stock_index(db, stock_tracker)

    db.commit()

    summary = {
        "china_funds_fetched": len(china_results),
        "sec_13f_fetched": len(sec_results),
        "gurus_updated": updated_gurus,
        "total_holdings": total_holdings,
        "stocks_indexed": stock_count,
    }
    logger.info(f"Guru holdings update complete: {summary}")
    return summary
