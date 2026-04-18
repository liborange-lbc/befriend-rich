import logging
from datetime import date, timedelta

import pandas as pd

from app.services.market_data.base import DataSourceAdapter

logger = logging.getLogger(__name__)


class YahooAdapter(DataSourceAdapter):
    def fetch_daily_prices(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
            ticker = yf.Ticker(code)
            df = ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
            )
            if df.empty:
                return pd.DataFrame(columns=["date", "close"])
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["Date"]).dt.date
            df["close"] = df["Close"]
            return df[["date", "close"]].sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Yahoo fetch failed for {code}: {e}")
            return pd.DataFrame(columns=["date", "close"])

    def fetch_exchange_rate(
        self, pair: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
            symbol = pair.replace("/", "") + "=X"
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
            )
            if df.empty:
                return pd.DataFrame(columns=["date", "rate"])
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["Date"]).dt.date
            df["rate"] = df["Close"]
            return df[["date", "rate"]].sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Yahoo exchange rate fetch failed for {pair}: {e}")
            return pd.DataFrame(columns=["date", "rate"])
