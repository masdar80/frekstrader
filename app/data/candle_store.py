import os
import pandas as pd
from typing import Dict

class CandleStore:
    """
    In-memory cache and retriever for Parquet historical data files.
    """
    def __init__(self, store_dir: str = "app/data/store"):
        self.store_dir = store_dir
        self._cache: Dict[str, pd.DataFrame] = {}
        
    def load(self, symbol: str, timeframe: str) -> pd.DataFrame:
        key = f"{symbol}_{timeframe}"
        if key in self._cache:
            return self._cache[key]
            
        file_path = os.path.join(self.store_dir, f"{key}.parquet")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Parquet data not found for {symbol} ({timeframe}). Run historical ingestor first.")
            
        df = pd.read_parquet(file_path)
        self._cache[key] = df
        return df
        
    def get_slice(self, symbol: str, timeframe: str, start_dt=None, end_dt=None) -> pd.DataFrame:
        df = self.load(symbol, timeframe)
        if start_dt:
            start_dt = pd.to_datetime(start_dt)
        if end_dt:
            end_dt = pd.to_datetime(end_dt)
            
        if start_dt and end_dt:
            return df[(df.index >= start_dt) & (df.index <= end_dt)]
        elif start_dt:
            return df[df.index >= start_dt]
        elif end_dt:
            return df[df.index <= end_dt]
        return df

candle_store = CandleStore()
