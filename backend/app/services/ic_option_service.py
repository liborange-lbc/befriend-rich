"""IC期权（中证500股指期货）数据获取与统计服务。

数据源：
- 中证500指数：东方财富 kline API
- IC期货合约：akshare futures_zh_daily_sina（逐合约获取后按日期映射为当月/下月/当季/下季连续序列）
"""

import calendar
import logging
import math
import time
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.models.ic_option import ICOptionPrice

logger = logging.getLogger(__name__)

CONTRACT_TYPES = ["index", "current_month", "next_month", "current_quarter", "next_quarter"]
CONTRACT_LABELS = {
    "index": "中证500",
    "current_month": "当月",
    "next_month": "下月",
    "current_quarter": "当季",
    "next_quarter": "下季",
}
IC_MULTIPLIER = 200  # 元/点



# ── 合约映射逻辑 ──────────────────────────────────────────


def _get_third_friday(year: int, month: int) -> date:
    """获取某月第三个周五。"""
    cal = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in cal if week[4] != 0]
    return date(year, month, fridays[2])


def _next_ym(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _contract_code(year: int, month: int) -> str:
    """生成合约代码，如 IC2504。"""
    return f"IC{year % 100:02d}{month:02d}"


def get_contract_map_for_date(trade_date: date) -> dict[str, str]:
    """给定交易日，返回 {contract_type: contract_code} 映射。"""
    third_fri = _get_third_friday(trade_date.year, trade_date.month)
    if trade_date <= third_fri:
        cy, cm = trade_date.year, trade_date.month
    else:
        cy, cm = _next_ym(trade_date.year, trade_date.month)

    # 当月
    m1 = (cy, cm)
    # 下月
    ny, nm = _next_ym(cy, cm)
    m2 = (ny, nm)

    # 当季：严格在下月之后的最近季月
    quarter_months = [3, 6, 9, 12]
    cq = None
    for qm in quarter_months:
        if (cy, qm) > m2:
            cq = (cy, qm)
            break
    if cq is None:
        cq = (cy + 1, 3)

    # 下季
    qi = quarter_months.index(cq[1])
    if qi + 1 < len(quarter_months):
        nq = (cq[0], quarter_months[qi + 1])
    else:
        nq = (cq[0] + 1, quarter_months[0])

    return {
        "current_month": _contract_code(*m1),
        "next_month": _contract_code(*m2),
        "current_quarter": _contract_code(*cq),
        "next_quarter": _contract_code(*nq),
    }


# ── 数据获取 ──────────────────────────────────────────────


def _fetch_index_klines(start: str, end: str) -> list[dict]:
    """通过 akshare (sina) 获取中证500指数日K数据。"""
    try:
        import akshare as ak

        df = ak.stock_zh_index_daily(symbol="sh000905")
        if df is None or df.empty:
            return []
        start_d = datetime.strptime(start, "%Y%m%d").date()
        end_d = datetime.strptime(end, "%Y%m%d").date()
        results = []
        for _, row in df.iterrows():
            d = pd.Timestamp(row["date"]).date()
            if start_d <= d <= end_d:
                results.append({"date": d.isoformat(), "close": float(row["close"])})
        return results
    except Exception as e:
        logger.error(f"Fetch CSI500 index failed: {e}")
        return []


def _fetch_contract_data(symbol: str) -> dict[date, float]:
    """用 akshare 获取单个合约的日K数据，返回 {date: close_price}。"""
    try:
        import akshare as ak

        df = ak.futures_zh_daily_sina(symbol=symbol)
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            d = pd.Timestamp(row["date"]).date()
            result[d] = float(row["close"])
        return result
    except Exception as e:
        logger.warning(f"Fetch contract {symbol} failed: {e}")
        return {}


def _fetch_main_contract() -> dict[date, float]:
    """用 akshare 获取 IC 主力连续合约全部历史日K（2017 至今）。"""
    try:
        import akshare as ak

        df = ak.futures_main_sina(symbol="IC0")
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            d = pd.Timestamp(row["日期"]).date()
            result[d] = float(row["收盘价"])
        logger.info(f"Main contract IC0: {len(result)} rows")
        return result
    except Exception as e:
        logger.error(f"Fetch main contract IC0 failed: {e}")
        return {}


def _collect_needed_contracts(trading_dates: list[date]) -> set[str]:
    """从交易日列表中收集所有需要的合约代码。"""
    codes: set[str] = set()
    for d in trading_dates:
        mapping = get_contract_map_for_date(d)
        codes.update(mapping.values())
    return codes


def _fetch_all_contracts(codes: set[str], delay: float = 0.3) -> dict[str, dict[date, float]]:
    """批量获取所有合约数据。返回 {contract_code: {date: close_price}}。"""
    all_data: dict[str, dict[date, float]] = {}
    total = len(codes)
    for i, code in enumerate(sorted(codes)):
        logger.info(f"Fetching contract {code} ({i + 1}/{total})")
        data = _fetch_contract_data(code)
        if data:
            all_data[code] = data
        if i < total - 1:
            time.sleep(delay)
    return all_data


# ── 回填 & 日更 ──────────────────────────────────────────

# 新浪个别合约数据仅 2020 年起可用
_INDIVIDUAL_CONTRACT_START = date(2020, 1, 1)


def backfill_history(db: Session, years: int = 10) -> dict[str, int]:
    """回填历史数据。

    策略：
    - 中证500指数：akshare stock_zh_index_daily（全量）
    - 当月（主力）：futures_main_sina IC0（2017 至今）
    - 下月/当季/下季：个别合约映射（2020 至今，更早的数据新浪已不可查）
    """
    end = date.today()
    start = date(end.year - years, 1, 1)
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")

    counts: dict[str, int] = {}

    # 1) 中证500指数
    logger.info("Fetching CSI500 index...")
    index_rows = _fetch_index_klines(start_str, end_str)
    counts["index"] = _upsert_rows(db, "index", index_rows)
    db.commit()
    logger.info(f"Index: {counts['index']} rows upserted")

    # 2) 当月（主力连续）— 覆盖 2017 至今
    logger.info("Fetching main contract IC0 (当月/主力)...")
    main_data = _fetch_main_contract()
    main_rows = [
        {"date": d.isoformat(), "close": p, "code": "IC0(主力)"}
        for d, p in sorted(main_data.items())
    ]
    counts["current_month"] = _upsert_rows(db, "current_month", main_rows)
    db.commit()
    logger.info(f"current_month (main): {counts['current_month']} rows upserted")

    # 3) 下月/当季/下季 — 个别合约（2020 至今）
    trading_dates = [
        datetime.strptime(r["date"], "%Y-%m-%d").date()
        for r in index_rows
        if datetime.strptime(r["date"], "%Y-%m-%d").date() >= _INDIVIDUAL_CONTRACT_START
    ]
    logger.info(f"Building term structure for {len(trading_dates)} trading days (2020+)...")

    needed = _collect_needed_contracts(trading_dates)
    logger.info(f"Need {len(needed)} unique contracts")
    contract_data = _fetch_all_contracts(needed)
    logger.info(f"Fetched {len(contract_data)} contracts with data")

    # 同时用个别合约覆盖当月（比主力连续更精确）
    for ctype in ["current_month", "next_month", "current_quarter", "next_quarter"]:
        mapped_rows = []
        for d in trading_dates:
            mapping = get_contract_map_for_date(d)
            code = mapping[ctype]
            prices = contract_data.get(code, {})
            price = prices.get(d)
            if price and price > 0:
                mapped_rows.append({"date": d.isoformat(), "close": price, "code": code})
        cnt = _upsert_rows(db, ctype, mapped_rows)
        counts[ctype] = counts.get(ctype, 0) + cnt
        logger.info(f"{ctype}: {len(mapped_rows)} mapped, {cnt} upserted")

    db.commit()
    return counts


def fetch_and_store(db: Session, days: int = 7) -> dict[str, int]:
    """获取最近 N 天数据并存储（补漏 + 更新当天）。"""
    end = date.today()
    start = end - timedelta(days=days + 10)
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")

    counts: dict[str, int] = {}

    # 1) 中证500指数
    index_rows = _fetch_index_klines(start_str, end_str)
    counts["index"] = _upsert_rows(db, "index", index_rows)

    # 2) 确定最近的活跃合约
    trading_dates = [
        datetime.strptime(r["date"], "%Y-%m-%d").date()
        for r in index_rows
    ]
    if not trading_dates:
        db.commit()
        return counts

    needed = _collect_needed_contracts(trading_dates)
    contract_data = _fetch_all_contracts(needed, delay=0.2)

    for ctype in ["current_month", "next_month", "current_quarter", "next_quarter"]:
        mapped_rows = []
        for d in trading_dates:
            mapping = get_contract_map_for_date(d)
            code = mapping[ctype]
            prices = contract_data.get(code, {})
            price = prices.get(d)
            if price and price > 0:
                mapped_rows.append({"date": d.isoformat(), "close": price, "code": code})
        counts[ctype] = _upsert_rows(db, ctype, mapped_rows)

    db.commit()
    return counts


def _upsert_rows(db: Session, contract_type: str, rows: list[dict]) -> int:
    """Insert or update price rows. Returns count of affected rows."""
    count = 0
    for row in rows:
        d = row["date"]
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date() if "-" in d else datetime.strptime(d, "%Y%m%d").date()
        price = row["close"]
        if price <= 0:
            continue
        code = row.get("code")

        existing = (
            db.query(ICOptionPrice)
            .filter(ICOptionPrice.date == d, ICOptionPrice.contract_type == contract_type)
            .first()
        )
        if existing:
            if existing.close_price != price:
                existing.close_price = price
                existing.contract_code = code
                count += 1
        else:
            db.add(ICOptionPrice(
                date=d, contract_type=contract_type,
                close_price=price, contract_code=code,
            ))
            count += 1
    return count


# ── 查询 ──────────────────────────────────────────────


def get_prices(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """获取价格数据，按日期聚合为宽表格式。"""
    query = db.query(ICOptionPrice)
    if start_date:
        query = query.filter(ICOptionPrice.date >= start_date)
    if end_date:
        query = query.filter(ICOptionPrice.date <= end_date)
    rows = query.order_by(ICOptionPrice.date).all()

    by_date: dict[date, dict] = {}
    for r in rows:
        if r.date not in by_date:
            by_date[r.date] = {"date": r.date.isoformat()}
        by_date[r.date][r.contract_type] = r.close_price

    return sorted(by_date.values(), key=lambda x: x["date"])


# ── 统计 ──────────────────────────────────────────────


def _get_expiry_date(trade_date: date, contract_type: str) -> date | None:
    """计算给定交易日某合约类型的到期日（第三个周五）。"""
    if contract_type == "index":
        return None
    mapping = get_contract_map_for_date(trade_date)
    code = mapping.get(contract_type)
    if not code:
        return None
    # 从合约代码解析到期年月
    yy = int(code[2:4])
    mm = int(code[4:6])
    year = 2000 + yy
    return _get_third_friday(year, mm)


def calculate_statistics(prices: list[dict]) -> list[dict]:
    """计算各合约的价差和年化统计。"""
    if not prices:
        return []

    futures_types = ["current_month", "next_month", "current_quarter", "next_quarter"]
    results = []

    for ctype in futures_types:
        paired = []
        for row in prices:
            idx_price = row.get("index")
            fut_price = row.get(ctype)
            if idx_price and fut_price:
                d = date.fromisoformat(row["date"]) if isinstance(row["date"], str) else row["date"]
                expiry = _get_expiry_date(d, ctype)
                days_to_expiry = (expiry - d).days if expiry else 30
                if days_to_expiry <= 0:
                    days_to_expiry = 1
                spread = idx_price - fut_price
                annual_rate = (spread / idx_price) / (days_to_expiry / 365) * 100
                paired.append({"date": d, "spread": spread, "annual": annual_rate})

        if not paired:
            results.append({
                "contract_type": ctype,
                "label": CONTRACT_LABELS[ctype],
            })
            continue

        def _avg(items: list[dict], key: str) -> float | None:
            vals = [i[key] for i in items if i[key] is not None and not math.isnan(i[key]) and not math.isinf(i[key])]
            return round(sum(vals) / len(vals), 4) if vals else None

        latest = paired[-1]
        last_22 = paired[-22:] if len(paired) >= 22 else paired
        last_252 = paired[-252:] if len(paired) >= 252 else paired
        last_756 = paired[-756:] if len(paired) >= 756 else paired

        results.append({
            "contract_type": ctype,
            "label": CONTRACT_LABELS[ctype],
            "spread_current": round(latest["spread"], 2),
            "annual_current": round(latest["annual"], 4),
            "annual_1m": _avg(last_22, "annual"),
            "annual_1y": _avg(last_252, "annual"),
            "annual_3y": _avg(last_756, "annual"),
            "annual_all": _avg(paired, "annual"),
        })

    return results


def calculate_roll_guidance(prices: list[dict]) -> dict:
    """计算换仓指引。

    展示内容：
    1. 当月合约到期倒计时 + 建议换仓窗口
    2. 各换仓路径：展期价差、年化收益、与历史均值对比
    3. 综合建议
    """
    if not prices:
        return {}

    # 取最新一条有完整数据的行
    latest = None
    for row in reversed(prices):
        if row.get("index") and row.get("current_month"):
            latest = row
            break
    if not latest:
        return {}

    today = date.fromisoformat(latest["date"]) if isinstance(latest["date"], str) else latest["date"]
    idx = latest["index"]
    types = ["current_month", "next_month", "current_quarter", "next_quarter"]

    # 收集合约信息
    contracts: list[dict] = []
    for t in types:
        p = latest.get(t)
        expiry = _get_expiry_date(today, t)
        mapping = get_contract_map_for_date(today)
        code = mapping.get(t, "")
        days_left = (expiry - today).days if expiry else None
        basis = round(idx - p, 2) if p else None
        contracts.append({
            "type": t,
            "label": CONTRACT_LABELS[t],
            "code": code,
            "price": p,
            "expiry": expiry.isoformat() if expiry else None,
            "days_left": days_left,
            "basis": basis,
        })

    # 换仓路径分析（从当月出发到其他三个合约）
    cm = contracts[0]  # 当月
    paths: list[dict] = []
    for target in contracts[1:]:
        if not cm["price"] or not target["price"] or not cm["days_left"] or not target["days_left"]:
            continue
        day_diff = target["days_left"] - cm["days_left"]
        if day_diff <= 0:
            day_diff = 1
        spread_pts = round(cm["price"] - target["price"], 2)  # 近月 - 远月
        annual = round((spread_pts / idx) / (day_diff / 365) * 100, 2)

        # 计算历史同路径年化均值（从 prices 中计算最近 252 天）
        hist_annuals = []
        for row in prices[-252:]:
            ri = row.get("index")
            rn = row.get("current_month")
            rf = row.get(target["type"])
            if ri and rn and rf:
                rd = date.fromisoformat(row["date"]) if isinstance(row["date"], str) else row["date"]
                re_near = _get_expiry_date(rd, "current_month")
                re_far = _get_expiry_date(rd, target["type"])
                if re_near and re_far:
                    dd = (re_far - re_near).days
                    if dd > 0:
                        ha = ((rn - rf) / ri) / (dd / 365) * 100
                        if not math.isinf(ha) and not math.isnan(ha):
                            hist_annuals.append(ha)
        hist_avg = round(sum(hist_annuals) / len(hist_annuals), 2) if hist_annuals else None

        # 判断当前 vs 历史
        vs_hist = None
        if hist_avg is not None and hist_avg != 0:
            vs_hist = round(annual - hist_avg, 2)

        paths.append({
            "from": cm["label"],
            "from_code": cm["code"],
            "to": target["label"],
            "to_code": target["code"],
            "spread_pts": spread_pts,
            "annual": annual,
            "hist_avg": hist_avg,
            "vs_hist": vs_hist,
            "day_diff": day_diff,
        })

    # 换仓建议
    days_left = cm["days_left"] or 0
    if days_left <= 3:
        timing = "urgent"
        timing_text = f"当月合约 {cm['code']} 仅剩 {days_left} 天到期，需立即换仓"
    elif days_left <= 10:
        timing = "optimal"
        timing_text = f"当月合约 {cm['code']} 剩余 {days_left} 天，处于最佳换仓窗口（到期前5-10个交易日）"
    else:
        timing = "wait"
        timing_text = f"当月合约 {cm['code']} 剩余 {days_left} 天到期，可继续持有观察展期价差"

    # 找最优路径
    best = max(paths, key=lambda p: p["annual"]) if paths else None
    if best:
        recommend = f"当前最优路径：{best['from_code']} → {best['to_code']}（{best['to']}），年化 {best['annual']:+.2f}%"
        if best["vs_hist"] is not None:
            if best["vs_hist"] > 1:
                recommend += f"，高于历史均值 {abs(best['vs_hist']):.2f}pp，展期时机较好"
            elif best["vs_hist"] < -1:
                recommend += f"，低于历史均值 {abs(best['vs_hist']):.2f}pp，可等待更优价差"
            else:
                recommend += "，接近历史均值水平"
    else:
        recommend = "数据不足，无法给出建议"

    return {
        "expiry": cm["expiry"],
        "days_left": days_left,
        "timing": timing,
        "timing_text": timing_text,
        "recommend": recommend,
        "contracts": contracts,
        "paths": paths,
    }


def calculate_position(
    entry_point: float,
    entry_capital: float = 500000,
    margin_rate: float = 0.12,
    num_contracts: int | None = None,
) -> dict:
    """计算持仓信息：手数、保证金点位、爆仓点位。"""
    contract_value = entry_point * IC_MULTIPLIER
    margin_per = contract_value * margin_rate
    if num_contracts is not None and num_contracts >= 1:
        n = num_contracts
    else:
        n = int(entry_capital // margin_per) if margin_per > 0 else 0
        if n <= 0:
            n = 1
    total_margin = n * margin_per
    remaining = entry_capital - total_margin

    # 最低保证金点位（做多）：equity == required margin
    denom = n * IC_MULTIPLIER * (1 - margin_rate)
    margin_call = (n * IC_MULTIPLIER * entry_point - entry_capital) / denom if denom else 0

    # 爆仓点位（做多）：equity == 0
    liquidation = entry_point - entry_capital / (n * IC_MULTIPLIER) if n > 0 else 0

    return {
        "entry_point": entry_point,
        "entry_capital": entry_capital,
        "margin_rate": margin_rate,
        "multiplier": IC_MULTIPLIER,
        "contract_value": round(contract_value, 2),
        "margin_per_contract": round(margin_per, 2),
        "num_contracts": n,
        "total_margin": round(total_margin, 2),
        "remaining_capital": round(remaining, 2),
        "margin_call_point": round(margin_call, 2),
        "liquidation_point": round(liquidation, 2),
    }
