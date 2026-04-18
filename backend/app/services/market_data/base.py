from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataSourceAdapter(ABC):
    @abstractmethod
    def fetch_daily_prices(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Fetch daily prices. Returns DataFrame with columns: date, close."""

    @abstractmethod
    def fetch_exchange_rate(
        self, pair: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Fetch exchange rates. Returns DataFrame with columns: date, rate."""
