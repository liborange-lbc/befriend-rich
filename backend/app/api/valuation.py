"""估值指标 API — 基于指数 PE 历史分位数的温度计和定投系数。"""

import json
import logging
import re
import subprocess

from fastapi import APIRouter, HTTPException, Query

from app.response import ok
from app.services.valuation_service import (
    INDEX_INFO,
    compute_valuation_from_kline,
    get_dca_coefficient_table,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Reuse the kline fetching logic from market_insight
_INDEX_SINA_SYMBOL = {
    "000016": "sh000016", "000300": "sh000300", "000905": "sh000905",
    "000852": "sh000852", "399006": "sz399006", "000688": "sh000688",
    "000932": "sh000932", "000933": "sh000933", "399986": "sz399986",
    "399808": "sz399808", "000993": "sh000993",
    "000922": "sh000922", "000015": "sh000015", "399324": "sz399324",
}


def _fetch_kline_with_pe(code: str) -> list[dict]:
    """Fetch index kline + PE data. Returns list of {date, close, pe}."""
    symbol = _INDEX_SINA_SYMBOL.get(code)
    if not symbol:
        return []

    kline_map: dict[str, dict] = {}
    try:
        url = (
            f"https://quotes.sina.cn/cn/api/jsonp_v2.php/=/"
            f"CN_MarketDataService.getKLineData?symbol={symbol}"
            f"&scale=240&ma=no&datalen=1970"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20,
        )
        m = re.search(r"=\((\[.*\])\)", result.stdout or "")
        if m:
            for it in json.loads(m.group(1)):
                kline_map[it["day"]] = {"date": it["day"], "close": float(it["close"]), "pe": None}
    except Exception as e:
        logger.warning(f"Failed to fetch kline for {code}: {e}")

    if not kline_map:
        return []

    # Fetch PE from CSIndex
    dates = sorted(kline_map.keys())
    start_year = int(dates[0][:4])
    end_year = int(dates[-1][:4])

    for year in range(start_year, end_year + 1):
        pe_url = (
            f"https://www.csindex.com.cn/csindex-home/perf/index-perf"
            f"?indexCode={code}&startDate={year}0101&endDate={year}1231"
        )
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "10", "-H", "User-Agent: Mozilla/5.0", pe_url],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                pe_data = json.loads(result.stdout)
                for item in pe_data.get("data", []):
                    td = item.get("tradeDate", "")
                    if len(td) >= 8:
                        day = f"{td[:4]}-{td[4:6]}-{td[6:8]}"
                        if day in kline_map and item.get("peg") is not None:
                            kline_map[day]["pe"] = round(float(item["peg"]), 2)
        except Exception:
            pass

    return sorted(kline_map.values(), key=lambda x: x["date"])


@router.get("/indices")
def api_valuation_indices():
    """支持的指数列表。"""
    return ok([{"code": k, "name": v} for k, v in INDEX_INFO.items()])


@router.get("/history/{index_code}")
def api_valuation_history(index_code: str):
    """指定指数的 PE 历史 + 分位数 + 温度。"""
    if index_code not in INDEX_INFO:
        raise HTTPException(status_code=404, detail="不支持的指数")

    kline = _fetch_kline_with_pe(index_code)
    result = compute_valuation_from_kline(kline)
    if not result:
        return ok(None, meta={"message": "PE 数据不足"})

    return ok({
        "index_code": index_code,
        "index_name": INDEX_INFO[index_code],
        **result,
    })


@router.get("/temperature")
def api_valuation_temperature():
    """所有指数的估值温度概览（较慢，需逐一获取PE数据）。"""
    results = []
    for code, name in INDEX_INFO.items():
        kline = _fetch_kline_with_pe(code)
        val = compute_valuation_from_kline(kline)
        if val:
            results.append({
                "index_code": code,
                "index_name": name,
                "current_pe": val["current_pe"],
                "pe_percentile": val["pe_percentile"],
                "temperature": val["temperature"],
                "dca_coefficient": val["dca_coefficient"],
                "dca_label": val["dca_label"],
            })
    return ok(results)


@router.get("/dca-coefficient")
def api_dca_coefficient():
    """定投系数对照表。"""
    return ok(get_dca_coefficient_table())
