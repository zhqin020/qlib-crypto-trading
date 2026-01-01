
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import json
import pandas as pd
from typing import Dict, Any

# Add src to Pypath
# live_loop.py is in src/serving (2 parents to src, 3 parents to project root)
# Actually:
# __file__ = .../src/serving/live_loop.py
# parent = .../src/serving
# parent.parent = .../src
# parent.parent.parent = .../qlib-crypto (PROJECT_ROOT)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from serving.exchange import ExchangeConnector
from serving.oms import LocalOrderManager as OMS
from backtesting.strategies import CryptoLongShortStrategy
from regime.detector import MarketRegimeDetector, MarketRegime

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/live_loop.log")
    ]
)
logger = logging.getLogger("LiveLoop")

class LiveTradingLoop:
    def __init__(self):
        self.config = self._load_config()
        self.live_config = self.config.get("live", {})
        
        # 1. Exchange Connector (Data Source)
        self.exchange = ExchangeConnector(self.live_config.get("exchange", {}))
        
        # 2. OMS (Execution)
        db_url = os.getenv("DATABASE_URL", "postgresql://crypto_user:crypto@localhost:5432/qlib_crypto")
        self.oms = OMS(db_url, exchange_connector=self.exchange)
        
        # 3. Strategy & Detector
        # Note: In a real system, we load a Trained Model.
        # For this prototype, we will assume a Dummy Score or Load from file.
        # But we DO need the Strategy Class to manage selection logic 
        # (TopK, Threshold, Leverage, Regime).
        
        self.strategy_config = {
            "topk": 2,
            "signal_threshold": 0.5, # Reduced for testing? Default is 0.5
            "direction": "long-short",
            "leverage": 1.0,
            "instrument_config": self.config.get("trading", {}).get("instruments", {})
        }
        self.strategy = CryptoLongShortStrategy(signal=pd.DataFrame(), **self.strategy_config)
        self.strategy.detector = MarketRegimeDetector() # Use default EMA settings (20, 60)

    def _load_config(self):
        # PROJECT_ROOT is /home/watson/work/qlib-crypto
        # Config is in /home/watson/work/qlib-crypto/config
        with open(PROJECT_ROOT / "config" / "trading_params.json") as f:
            return json.load(f)

    async def run_once(self):
        """Single execution iteration"""
        logger.info(">>> Starting Live Cycle <<<")
        
        # 1. Sync Market Data (Prices) for Portfolio Valuation
        logger.info("Syncing Market Prices...")
        self.oms.sync_market_prices()
        
        # 2. Get Real-time Market Data for Prediction (Simulated here with Mock/Head)
        # In full prod, we would call:
        # data_downloader -> update Qlib bin -> model.predict(dataset)
        # Here we will MOCK the scores.
        
        # Mock Scores (e.g. BTC Bullish, ETH Bearish)
        # We fetch current price just to log it
        btc_ticker = self.exchange.exchange.fetch_ticker("BTC/USDT")
        eth_ticker = self.exchange.exchange.fetch_ticker("ETH/USDT")
        
        logger.info(f"BTC: {btc_ticker['last']}, ETH: {eth_ticker['last']}")
        
        # Construct Mock Scores (In reality this comes from Predictor)
        # Let's say: BTC Score = 2.0 (Strong Buy), ETH Score = -1.0 (Sell)
        # We need a Pandas Series
        scores = pd.Series({
            "BTC/USDT": 2.0,
            "ETH/USDT": -1.5,
            "PEPE/USDT": 0.1
        })
        
        # 3. Detect Regime (Mocked or computed on recent history)
        # We need OHLCV dataframe for detector.
        # Let's just mock the Regime for this prototype to test flow.
        self.strategy.detector.detect = lambda x: (MarketRegime.BULL, 1.0, {"price": btc_ticker['last']})
        
        # 4. Generate Target Weights
        # We pass empty position list because OMS handles position diffs.
        # Strategy wants `position` object from Qlib backtest usually.
        # We will mock the `position` object required by Strategy?
        # Actually `generate_target_weight_position` takes (score, current_position, ...)
        
        # Mock Qlib Position Object (Duck Typing)
        class MockQlibPos:
            def get_stock_list(self): return [] # We let OMS handle rebalance logic via weights
            
        target_weights = self.strategy.generate_target_weight_position(
            scores, 
            MockQlibPos(), 
            pd.Timestamp.now(), 
            pd.Timestamp.now()
        )
        
        if not target_weights:
            logger.info("Strategy returned No Trades (Stand Aside).")
            target_weights = {} # Close all? Or Hold?
            # If strategy returns {}, it usually means "Close All" or "No Signal".
            # In Qlib logic, if it returns empty, it means empty portfolio.
        
        logger.info(f"Target Weights: {target_weights}")
        
        # 5. Execute Rebalance via OMS
        # We need a price map
        current_prices = {
            "BTC/USDT": btc_ticker['last'],
            "ETH/USDT": eth_ticker['last'],
            "PEPE/USDT": 0.00001 # Mock
        }
        
        self.oms.execute_rebalance(target_weights, current_prices)
        
        logger.info(">>> Cycle Complete <<<")

    async def run_forever(self, interval=60):
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Cycle Failed: {e}", exc_info=True)
            
            logger.info(f"Sleeping {interval}s...")
            await asyncio.sleep(interval)

if __name__ == "__main__":
    loop = LiveTradingLoop()
    asyncio.run(loop.run_once()) # Run once for now
