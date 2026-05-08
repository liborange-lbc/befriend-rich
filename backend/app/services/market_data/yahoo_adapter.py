import logging
from datetime import date, timedelta

import pandas as pd
import requests

from app.services.market_data.base import DataSourceAdapter

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _fetch_chart(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Directly call Yahoo Finance chart API, bypassing yfinance crumb auth."""
    params = {
        "period1": int(pd.Timestamp(start_date).timestamp()),
        "period2": int(pd.Timestamp(end_date + timedelta(days=1)).timestamp()),
        "interval": "1d",
    }
    resp = requests.get(
        _CHART_URL.format(symbol=symbol),
        params=params,
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    result = data.get("chart", {}).get("result")
    if not result:
        error = data.get("chart", {}).get("error", {})
        logger.warning(f"Yahoo chart empty for {symbol}: {error}")
        return pd.DataFrame()
    timestamps = result[0].get("timestamp", [])
    closes = result[0]["indicators"]["quote"][0].get("close", [])
    if not timestamps:
        return pd.DataFrame()
    df = pd.DataFrame({"timestamp": timestamps, "close": closes})
    df["date"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
    return df[["date", "close"]].dropna(subset=["close"]).reset_index(drop=True)


class YahooAdapter(DataSourceAdapter):
    def fetch_daily_prices(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        try:
            df = _fetch_chart(code, start_date, end_date)
            if df.empty:
                return pd.DataFrame(columns=["date", "close"])
            return df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Yahoo fetch failed for {code}: {e}")
            return pd.DataFrame(columns=["date", "close"])

    def fetch_exchange_rate(
        self, pair: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        try:
            symbol = pair.replace("/", "") + "=X"
            df = _fetch_chart(symbol, start_date, end_date)
            if df.empty:
                return pd.DataFrame(columns=["date", "rate"])
            df = df.rename(columns={"close": "rate"})
            return df[["date", "rate"]].sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Yahoo exchange rate fetch failed for {pair}: {e}")
            return pd.DataFrame(columns=["date", "rate"])
