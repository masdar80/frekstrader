import os
import pandas as pd
from typing import Optional
from app.utils.logger import logger

class HistoricalDataIngestor:
    """
    Ingests CSV files containing historical candle data (Dukascopy/MT5 format)
    and saves them as Parquet files for fast backtesting.
    """
    
    def __init__(self, store_dir: str = "app/data/store"):
        self.store_dir = store_dir
        os.makedirs(self.store_dir, exist_ok=True)
        
    def ingest_csv(self, csv_path: str, symbol: str, timeframe: str) -> bool:
        """
        Reads a Dukascopy or MT5 exported CSV and saves it to Parquet.
        """
        try:
            logger.info(f"Ingesting CSV: {csv_path} for {symbol} ({timeframe})")
            
            df = pd.read_csv(csv_path)
            
            # Standardize column names
            col_map = {}
            for col in df.columns:
                lower_col = col.lower().strip("<>")
                if "date" in lower_col: col_map[col] = "date"
                elif "time" in lower_col: col_map[col] = "time"
                elif "open" in lower_col: col_map[col] = "open"
                elif "high" in lower_col: col_map[col] = "high"
                elif "low" in lower_col: col_map[col] = "low"
                elif "close" in lower_col: col_map[col] = "close"
                elif "vol" in lower_col and "tick" not in lower_col: col_map[col] = "volume"
                
            df.rename(columns=col_map, inplace=True)
            
            # Ensure required columns
            required = ["open", "high", "low", "close"]
            for req in required:
                if req not in df.columns:
                    logger.error(f"Missing required column: {req}. Found: {df.columns.tolist()}")
                    return False
                    
            if "date" in df.columns and "time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"])
            elif "time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["time"])
            elif "date" in df.columns:
                df["timestamp"] = pd.to_datetime(df["date"])
            else:
                logger.error("No date/time column found")
                return False
                
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
            
            cols_to_keep = ["open", "high", "low", "close"]
            if "volume" in df.columns:
                cols_to_keep.append("volume")
                
            df = df[cols_to_keep]
            
            out_file = os.path.join(self.store_dir, f"{symbol}_{timeframe}.parquet")
            df.to_parquet(out_file)
            logger.info(f"✅ Saved {len(df)} candles to {out_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest CSV: {e}")
            return False

historical_ingestor = HistoricalDataIngestor()
