import logging
from datetime import date

import pandas as pd

from app.services.config_service import get_config
from app.services.market_data.base import DataSourceAdapter

logger = logging.getLogger(__name__)


class TushareAdapter(DataSourceAdapter):
    def __init__(self):
        self._pro = None

    @property
    def pro(self):
        if self._pro is None:
            import tushare as ts
            token = get_config("tushare_token", "")
            if not token:
                raise ValueError("tushare_token 未配置，请在设置中填写")
            ts.set_token(token)
            self._pro = ts.pro_api()
        return self._pro

    def fetch_daily_prices(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        try:
            df = self.pro.fund_nav(
                ts_code=code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                df = self.pro.daily(
                    ts_code=code,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                )
            if df is None or df.empty:
                return pd.DataFrame(columns=["date", "close"])

            if "end_date" in df.columns:
                df = df.rename(columns={"end_date": "date", "unit_nav": "close"})
            elif "trade_date" in df.columns:
                df = df.rename(columns={"trade_date": "date"})

            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df[["date", "close"]].sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Tushare fetch failed for {code}: {e}")
            return pd.DataFrame(columns=["date", "close"])

    def fetch_exchange_rate(
        self, pair: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        return pd.DataFrame(columns=["date", "rate"])
