import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print("Testing imports...")
try:
    from app.core.ml.calibrator import ml_calibrator
    print("ml_calibrator loaded")
    
    from app.core.ml.lstm_model import lstm_timer
    print("lstm_timer loaded")
    
    from app.core.ml.rl_tuner import ParameterTuner
    print("rl_tuner loaded")
    
    from app.core.ml.sentiment_nn import neural_sentiment
    print("sentiment_nn loaded")
    
    from app.backtest.backtester import Backtester
    print("backtester loaded")
    
    from app.backtest.walk_forward import WalkForwardEngine
    print("walk_forward loaded")
    
    from app.backtest.monte_carlo import monte_carlo
    print("monte_carlo loaded")
    
    from app.monitoring.health_checker import health_checker
    print("health_checker loaded")
    
    from app.monitoring.alert_manager import alert_manager
    print("alert_manager loaded")
    
    from app.db.maintenance import db_maintenance
    print("db_maintenance loaded")
    
    from app.core.strategies.base import TrendFollowingStrategy
    print("strategies loaded")
    
    from app.workers.market_watcher import MarketWatcher
    print("market_watcher loaded")
    
    from app.core.brain.decision_engine import decision_engine
    print("decision_engine loaded")
    
    from app.core.risk.trailing_manager import TrailingStopManager
    print("trailing_manager loaded")
    
    print("\nALL IMPORTS SUCCESSFUL!")
    
except Exception as e:
    print(f"\nIMPORT ERROR: {e}")
    sys.exit(1)
