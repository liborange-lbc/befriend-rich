"""大盘洞察 API — 100×100 A股市值网格 + 指数行情"""

import json
import logging
import re
import subprocess
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.market_insight.grid import build_market_grid, refresh_market_data

logger = logging.getLogger(__name__)

router = APIRouter()

# 指数代码 → Sina 行情符号
_INDEX_SINA_SYMBOL = {
    "000016": "sh000016", "000300": "sh000300", "000905": "sh000905",
    "000852": "sh000852", "399006": "sz399006", "000688": "sh000688",
    "000932": "sh000932", "000933": "sh000933", "399986": "sz399986",
    "399808": "sz399808", "000993": "sh000993",
    "000922": "sh000922", "000015": "sh000015", "399324": "sz399324",
}

# CSIndex PE 支持的指数（399006/399324 无 PE）
_CSINDEX_PE_SUPPORTED = {
    "000016", "000300", "000905", "000852", "000688", "932000",
    "000932", "000933", "399986", "399808", "000993",
    "000922", "000015",
}


@router.get("/grid")
def get_market_grid(db: Session = Depends(get_db)) -> dict:
    """
    Get 100×100 A-share market cap grid with index overlays.
    Reads from DB snapshot, returns instantly.
    """
    result = build_market_grid(db)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return ok(result)


@router.get("/index-kline")
def get_index_kline(code: str = Query(..., description="指数代码，如 000300")) -> dict:
    """获取指数近十年日K数据（日期 + 收盘价 + PE），最多 ~1970 条。"""
    symbol = _INDEX_SINA_SYMBOL.get(code)
    if not symbol:
        return ok([])

    # 1) Fetch close prices from Sina (max ~1970 records ≈ 8 years)
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
        return ok([])

    # 2) Fetch PE from CSIndex (batched by year to stay within API limits)
    if code in _CSINDEX_PE_SUPPORTED:
        dates = sorted(kline_map.keys())
        start_year = int(dates[0][:4])
        end_year = int(dates[-1][:4])

        for year in range(start_year, end_year + 1):
            y_start = f"{year}0101"
            y_end = f"{year}1231"
            pe_url = (
                f"https://www.csindex.com.cn/csindex-home/perf/index-perf"
                f"?indexCode={code}&startDate={y_start}&endDate={y_end}"
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
            except Exception as e:
                logger.warning(f"Failed to fetch PE for {code} year {year}: {e}")

    return ok(sorted(kline_map.values(), key=lambda x: x["date"]))


@router.post("/refresh")
def post_refresh_market_data(db: Session = Depends(get_db)) -> dict:
    """Trigger a background refresh of market data from remote APIs."""
    from app.database import SessionLocal

    def _refresh():
        s = SessionLocal()
        try:
            refresh_market_data(s)
        except Exception as e:
            logger.error(f"Market data refresh failed: {e}")
        finally:
            s.close()

    threading.Thread(target=_refresh, daemon=True).start()
    return ok({"message": "刷新已开始，请稍后查看"})
