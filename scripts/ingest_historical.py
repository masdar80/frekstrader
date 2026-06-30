import sys
import os
import glob
import re

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.historical_fetcher import historical_ingestor
from app.utils.logger import logger

def main():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.exists(data_dir):
        logger.error(f"Data directory not found at: {data_dir}")
        sys.exit(1)

    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        logger.warning(f"No CSV files found in: {data_dir}")
        sys.exit(0)

    # Pairs we want to support
    valid_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]
    
    # Map MT5 timeframes in filename to our timeframe keys
    tf_map = {
        "M15": "15m",
        "H1": "1h",
        "H4": "4h",
        "Daily": "1d"
    }

    success_count = 0
    fail_count = 0

    for filepath in csv_files:
        filename = os.path.basename(filepath)
        
        # Try to identify pair and timeframe from filename
        # Format example: AUDUSD_H1_202401020000_202606301200.csv
        found_pair = None
        for pair in valid_pairs:
            if filename.startswith(pair):
                found_pair = pair
                break
                
        if not found_pair:
            continue
            
        found_tf = None
        for mt_tf, app_tf in tf_map.items():
            if f"_{mt_tf}_" in filename or f"_{mt_tf}." in filename:
                found_tf = app_tf
                break
                
        if not found_tf:
            logger.warning(f"Could not identify timeframe in filename: {filename}")
            continue

        res = historical_ingestor.ingest_csv(filepath, found_pair, found_tf)
        if res:
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"🎉 Ingestion finished! Successful: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
