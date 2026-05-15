"""美股交易额榜单 Top30 — 每日抓取 + 趋势分析"""

import logging
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.us_stock_trend import USStockVolumeRanking

logger = logging.getLogger(__name__)

# 分析时回看天数
LOOKBACK_DAYS = 10


# 候选池：主要美股标的（S&P500 大市值 + 热门中概 + 热门成长/Meme）
_CANDIDATE_SYMBOLS = [
    # Mega-cap tech
    "AAPL.US", "MSFT.US", "NVDA.US", "GOOG.US", "AMZN.US", "META.US", "TSLA.US",
    "AVGO.US", "ORCL.US", "CRM.US", "ADBE.US", "AMD.US", "INTC.US", "QCOM.US",
    "TXN.US", "MU.US", "AMAT.US", "LRCX.US", "KLAC.US", "MRVL.US", "ON.US",
    "ARM.US", "SMCI.US", "PLTR.US", "SNOW.US", "CRWD.US", "PANW.US", "ZS.US",
    "NET.US", "DDOG.US", "INTU.US",
    # Financials / conglomerate
    "BRK.B.US", "JPM.US", "V.US", "MA.US", "BAC.US", "GS.US", "MS.US",
    # Consumer / retail
    "COST.US", "WMT.US", "HD.US", "LOW.US", "NKE.US", "SBUX.US", "MCD.US",
    "PG.US", "KO.US", "PEP.US", "DIS.US", "NFLX.US", "SPOT.US", "ABNB.US",
    "BKNG.US", "UBER.US", "SHOP.US",
    # Healthcare / pharma
    "LLY.US", "UNH.US", "JNJ.US", "ABBV.US", "MRK.US",
    # Energy / industrial
    "XOM.US", "CVX.US", "GE.US", "CEG.US", "VST.US",
    # Fintech / crypto-adjacent
    "PYPL.US", "SQ.US", "COIN.US", "HOOD.US", "SOFI.US", "MSTR.US",
    "MARA.US", "RIOT.US",
    # EV
    "RIVN.US",
    # China ADR
    "PDD.US", "BABA.US", "JD.US", "NIO.US", "XPEV.US", "LI.US", "FUTU.US",
    "BILI.US", "TME.US",
    # Leveraged / popular ETF
    "SOXL.US", "TQQQ.US", "SQQQ.US", "SPY.US", "QQQ.US", "VOO.US",
    "YINN.US", "YANG.US",
    # Other popular
    "SNAP.US", "ROKU.US", "DKNG.US", "TTD.US",
]


def fetch_and_store_top30(db: Session) -> dict:
    """从长桥 API 获取美股成交额 Top30 并存入数据库。"""
    import os
    from pathlib import Path

    today = date.today()

    existing = (
        db.query(USStockVolumeRanking)
        .filter(USStockVolumeRanking.date == today)
        .count()
    )
    if existing >= 30:
        return {"status": "skipped", "message": f"{today} 数据已存在"}

    # Init Longbridge
    try:
        os.environ["HOME"] = os.environ.get("HOME", "/root")
        client_id_file = Path.home() / ".longbridge" / "openapi" / "client_id"
        if not client_id_file.exists():
            return {"status": "error", "message": "长桥 OAuth 未配置"}

        client_id = client_id_file.read_text().strip()
        from longbridge.openapi import CalcIndex, Config, OAuthBuilder, QuoteContext

        oauth = OAuthBuilder(client_id).build(lambda url: None)
        config = Config.from_oauth(oauth)
        ctx = QuoteContext(config)
    except Exception as e:
        logger.error(f"Longbridge init failed: {e}")
        return {"status": "error", "message": str(e)}

    # Fetch volume/turnover for candidate pool
    try:
        indexes = [
            CalcIndex.Volume, CalcIndex.Turnover, CalcIndex.LastDone,
            CalcIndex.ChangeRate, CalcIndex.TotalMarketValue,
        ]
        result = ctx.calc_indexes(_CANDIDATE_SYMBOLS, indexes)
    except Exception as e:
        logger.error(f"Longbridge calc_indexes failed: {e}")
        return {"status": "error", "message": str(e)}

    # Build items and sort by turnover
    items = []
    for r in result:
        turnover = float(r.turnover) if r.turnover else 0
        if turnover <= 0:
            continue
        items.append({
            "ticker": r.symbol.replace(".US", ""),
            "name": "",  # Will be filled by static_info
            "volume": turnover,  # store turnover as volume for consistency
            "price": float(r.last_done) if r.last_done else None,
            "change_pct": float(r.change_rate) if r.change_rate else None,
            "market_cap": float(r.total_market_value) if r.total_market_value else None,
        })

    items.sort(key=lambda x: x["volume"], reverse=True)
    top30 = items[:30]

    if not top30:
        return {"status": "error", "message": "无成交数据（可能非交易时间）"}

    # Fetch names via static_info
    try:
        top_symbols = [it["ticker"] + ".US" for it in top30]
        infos = ctx.static_info(top_symbols)
        name_map = {info.symbol.replace(".US", ""): info.name_cn or info.name_en for info in infos}
        for it in top30:
            it["name"] = name_map.get(it["ticker"], it["ticker"])
    except Exception as e:
        logger.warning(f"Failed to fetch static_info for names: {e}")
        for it in top30:
            it["name"] = it["name"] or it["ticker"]

    # Write to DB
    db.query(USStockVolumeRanking).filter(
        USStockVolumeRanking.date == today
    ).delete()

    records = []
    for i, it in enumerate(top30, 1):
        rec = USStockVolumeRanking(
            date=today,
            rank=i,
            ticker=it["ticker"],
            name=it["name"],
            volume=it["volume"],
            price=it["price"],
            change_pct=it["change_pct"],
            market_cap=it["market_cap"],
        )
        db.add(rec)
        records.append(rec)

    db.commit()
    logger.info(f"US stock top30 saved for {today}: {len(records)} records (via Longbridge)")
    return {"status": "ok", "count": len(records)}


def get_ranking_with_analysis(db: Session) -> dict:
    """获取最新榜单 + 趋势分析（新进入 / 快速上升 / 持续稳定）。"""
    # 最新日期
    latest_date = (
        db.query(func.max(USStockVolumeRanking.date)).scalar()
    )
    if not latest_date:
        return {"date": None, "ranking": [], "insights": []}

    # 最新榜单
    latest = (
        db.query(USStockVolumeRanking)
        .filter(USStockVolumeRanking.date == latest_date)
        .order_by(USStockVolumeRanking.rank)
        .all()
    )

    # 历史数据（回看 N 天）
    start_date = latest_date - timedelta(days=LOOKBACK_DAYS)
    history = (
        db.query(USStockVolumeRanking)
        .filter(USStockVolumeRanking.date >= start_date)
        .order_by(USStockVolumeRanking.date, USStockVolumeRanking.rank)
        .all()
    )

    # 按日期分组
    by_date: dict[date, list[USStockVolumeRanking]] = {}
    for r in history:
        by_date.setdefault(r.date, []).append(r)

    sorted_dates = sorted(by_date.keys())
    prev_date = sorted_dates[-2] if len(sorted_dates) >= 2 else None

    # 上一交易日的 ticker → rank
    prev_ranks: dict[str, int] = {}
    if prev_date:
        for r in by_date[prev_date]:
            prev_ranks[r.ticker] = r.rank

    # 历史出现天数统计
    ticker_days: dict[str, int] = {}
    for d, recs in by_date.items():
        if d == latest_date:
            continue
        for r in recs:
            ticker_days[r.ticker] = ticker_days.get(r.ticker, 0) + 1

    # 构造排名列表 + 标签
    ranking = []
    insights = []

    for r in latest:
        tags = []
        prev_rank = prev_ranks.get(r.ticker)
        days_in_top30 = ticker_days.get(r.ticker, 0)

        # 新进入：昨天不在 top30
        if prev_rank is None and prev_date:
            tags.append("new")

        # 快速上升：排名提升 >= 10
        if prev_rank is not None and prev_rank - r.rank >= 10:
            tags.append("rising")

        # 持续稳定：历史 N 天中出现 >= 60%
        history_days = len(sorted_dates) - 1  # 不算当天
        if history_days > 0 and days_in_top30 / history_days >= 0.6:
            tags.append("stable")

        item = {
            "rank": r.rank,
            "ticker": r.ticker,
            "name": r.name,
            "volume": r.volume,
            "price": r.price,
            "change_pct": r.change_pct,
            "market_cap": r.market_cap,
            "prev_rank": prev_rank,
            "days_in_top30": days_in_top30,
            "tags": tags,
        }
        ranking.append(item)

        # 生成洞察
        if "new" in tags:
            change_desc = ""
            if r.change_pct is not None:
                direction = "涨" if r.change_pct > 0 else "跌"
                change_desc = f"，当日{direction}{abs(r.change_pct):.1f}%"
                if abs(r.change_pct) > 5:
                    change_desc += "，波动较大需关注"
            insights.append({
                "type": "new",
                "ticker": r.ticker,
                "name": r.name,
                "rank": r.rank,
                "text": f"{r.name}({r.ticker}) 新进入榜单第{r.rank}名{change_desc}",
            })
        elif "rising" in tags:
            jump = prev_rank - r.rank
            insights.append({
                "type": "rising",
                "ticker": r.ticker,
                "name": r.name,
                "rank": r.rank,
                "prev_rank": prev_rank,
                "text": f"{r.name}({r.ticker}) 排名上升{jump}位至第{r.rank}名，交易热度骤增",
            })

    # 持续稳定的放在最后汇总
    stable_stocks = [r for r in ranking if "stable" in r["tags"]]
    if stable_stocks:
        names = "、".join(s["name"] for s in stable_stocks[:5])
        suffix = f"等{len(stable_stocks)}只" if len(stable_stocks) > 5 else ""
        insights.append({
            "type": "stable",
            "text": f"{names}{suffix} 持续活跃在 Top30，市场关注度稳定",
            "stocks": [s["ticker"] for s in stable_stocks],
        })

    return {
        "date": str(latest_date),
        "total_history_days": len(sorted_dates),
        "ranking": ranking,
        "insights": insights,
    }


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        v = float(val)
        return v if v == v else None  # NaN check
    except (ValueError, TypeError):
        return None
