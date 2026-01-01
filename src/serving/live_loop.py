import asyncio
import logging
import os
import sys
import json
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from serving.exchange import ExchangeConnector
from serving.oms import LocalOrderManager as OMS
from backtesting.strategies import CryptoLongShortStrategy
from regime.detector import MarketRegimeDetector, MarketRegime

logger = logging.getLogger("LiveLoop")

class LiveTradingLoop:
    """
    Orchestrates the live trading cycle: 
    Market Sync -> Regime Detection -> Strategy Signal -> OMS Execution
    """
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path("config/trading_params.json")
        
        self.config_path = config_path
        self.config = self._load_config()
        self.live_config = self.config.get("live", {})
        
        # 1. Exchange Connector (Data Source)
        # Pass empty dict if no live config to use env vars
        exchange_config = self.live_config.get("exchange", {})
        self.exchange = ExchangeConnector(exchange_config)
        
        # 2. OMS (Execution)
        # Try to get DB URL from env, then from config
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            db_cfg = self.config.get("database", {})
            db_url = f"postgresql://{db_cfg.get('user')}:{db_cfg.get('password')}@{db_cfg.get('host', 'localhost')}:{db_cfg.get('port', 5432)}/{db_cfg.get('dbname')}"
        
        self.oms = OMS(db_url, exchange_connector=self.exchange)
        
        # 3. Strategy & Detector
        # Load strategy params from trading section
        trading_cfg = self.config.get("trading", {})
        self.strategy_config = {
            "topk": trading_cfg.get("topk", 2),
            "signal_threshold": trading_cfg.get("signal_threshold", 0.5),
            "direction": trading_cfg.get("direction", "long-short"),
            "leverage": trading_cfg.get("leverage", 1.0),
            "instrument_config": trading_cfg.get("instruments", {})
        }
        
        # Signal is empty as it will be fed per-cycle or fetched
        self.strategy = CryptoLongShortStrategy(signal=pd.DataFrame(), **self.strategy_config)
        self.strategy.detector = MarketRegimeDetector() 

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path) as f:
            return json.load(f)

    async def run_once(self):
        """Single execution iteration"""
        logger.info(">>> Starting Live Cycle <<<")
        
        try:
            # 1. Sync Market Data (Prices) for Portfolio Valuation
            logger.info("Syncing Market Prices...")
            self.oms.sync_market_prices()
            
            # 2. Prediction Step (Currently Mocked)
            # TODO: Integrate with model.predict()
            # For now, we fetch tickers to show we are live
            symbols = list(self.strategy_config["instrument_config"].keys())
            if not symbols:
                symbols = ["BTC/USDT", "ETH/USDT"]
            
            # Fetch real prices for active symbols
            current_prices = {}
            for symbol in symbols:
                try:
                    ticker = self.exchange.exchange.fetch_ticker(symbol)
                    current_prices[symbol] = ticker['last']
                except Exception as e:
                    logger.warning(f"Failed to fetch ticker for {symbol}: {e}")
                    # Use a default if missing
                    current_prices[symbol] = 0.0

            logger.info(f"Current Prices Sync: { {k: v for k, v in current_prices.items() if v > 0} }")
            
            # 3. Mock Scores (Next step: Real Predictor)
            # We favor BTC and ETH for now in this mock
            scores = pd.Series({
                "BTC/USDT": 0.8,
                "ETH/USDT": -0.6,
                "SOL/USDT": 0.1
            })
            
            # 4. Detect Regime (Real detection or mock for prototype)
            btc_price = current_prices.get("BTC/USDT", 0.0)
            # In a real system, we'd use the detector on recent OHLCV
            # For now, we set the force_regime to BULL to test the strategy logic
            self.strategy.force_regime = MarketRegime.BULL
            
            # 5. Generate Target Weights
            class MockQlibPos:
                def get_stock_list(self): return []
                
            target_weights = self.strategy.generate_target_weight_position(
                scores, 
                MockQlibPos(), 
                pd.Timestamp.now(), 
                pd.Timestamp.now()
            )
            
            if not target_weights:
                logger.info("Strategy returned No Trades (Stand Aside).")
                target_weights = {} 
            
            logger.info(f"Target Weights: {target_weights}")
            
            # 6. Execute Rebalance via OMS
            self.oms.execute_rebalance(target_weights, current_prices)
            
            logger.info(">>> Cycle Complete <<<")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
            raise

    async def run_forever(self, interval=3600):
        """Loop forever with fixed interval"""
        while True:
            start_time = time.time()
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Cycle failed: {e}")
            
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            logger.info(f"Cycle took {elapsed:.2f}s. Sleeping {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    # Test execution
    import time
    loop = LiveTradingLoop()
    asyncio.run(loop.run_once())
