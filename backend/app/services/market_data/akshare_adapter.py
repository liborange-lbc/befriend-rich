import logging
from datetime import date

import pandas as pd

from app.services.market_data.base import DataSourceAdapter

logger = logging.getLogger(__name__)


class AkshareAdapter(DataSourceAdapter):
    def fetch_daily_prices(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        try:
            import akshare as ak

            # 去掉可能的后缀 (.OF, .SZ 等)
            pure_code = code.split(".")[0]

            df = ak.fund_open_fund_info_em(symbol=pure_code, indicator="单位净值走势")
            if df is None or df.empty:
                return pd.DataFrame(columns=["date", "close"])

            df["date"] = pd.to_datetime(df["净值日期"]).dt.date
            df["close"] = df["单位净值"].astype(float)
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            return df[["date", "close"]].sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Akshare fetch failed for {code}: {e}")
            return pd.DataFrame(columns=["date", "close"])

    def fetch_exchange_rate(
        self, pair: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        return pd.DataFrame(columns=["date", "rate"])
