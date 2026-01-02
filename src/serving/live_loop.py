import sys
import json
import os
import pandas as pd
import time
import logging
import qlib
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

from serving.exchange import ExchangeConnector
from serving.oms import LocalOrderManager as OMS
from serving.predictor import QlibPredictor
from backtesting.strategies import CryptoLongShortStrategy
from regime.detector import MarketRegimeDetector, MarketRegime
from qlib.utils import init_instance_by_config

logger = logging.getLogger("LiveLoop")

class LiveTradingLoop:
    """
    Orchestrates the live trading cycle: 
    Market Sync -> Real Prediction (Alpha158) -> Regime Detection -> Strategy Signal -> OMS Execution
    """
    def __init__(self, config_path: str = "config/trading_params.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # 1. Initialize Qlib FIRST (required for some models)
        serving_cfg = self.config.get("serving", {})
        self.dataset_name = serving_cfg.get("dataset_name", "crypto_1h_future")
        self._init_qlib()
        
        # 2. Initialize Exchange
        logger.info("Initializing ExchangeConnector...")
        self.exchange = ExchangeConnector()
        
        # 3. OMS initialization
        logger.info("Initializing OMS...")
        db_cfg = self.config.get("database", {})
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            db_url = f"postgresql://{db_cfg.get('user')}:{db_cfg.get('password')}@{db_cfg.get('host', 'localhost')}:{db_cfg.get('port', 5432)}/{db_cfg.get('dbname')}"
        
        self.oms = OMS(db_url=db_url, exchange_connector=self.exchange)
        
        # 4. Predictor Initialization
        logger.info("Initializing Predictor...")
        model_path = Path(serving_cfg.get("model_path", ""))
        if not model_path.is_absolute():
            model_path = self.config_path.parent.parent / model_path
            
        self.predictor = QlibPredictor(model_path)
        self.feature_set = serving_cfg.get("feature_set", "alpha158_crypto_1h_future")

        # 5. Strategy Initialization
        logger.info("Initializing Strategy...")
        strat_cfg = self.config.get("trading", {})
        self.strategy = CryptoLongShortStrategy(
            signal=pd.DataFrame(), # Placeholder
            topk=self.config.get("backtest", {}).get("topk", 3),
            signal_threshold=strat_cfg.get("signal_threshold", 0),
            leverage=strat_cfg.get("leverage", 1.0),
            ranking_mode=strat_cfg.get("ranking_mode", "signal"),
            amplitude_window=strat_cfg.get("amplitude_window", 24),
            instrument_config=strat_cfg.get("instruments", {})
        )
        logger.info("LiveTradingLoop __init__ done.")

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r") as f:
            return json.load(f)

    def _init_qlib(self):
        qlib_dir = self.config_path.parent.parent / "data" / "qlib" / self.dataset_name
        if not qlib_dir.exists():
            # Fallback to general qlib dir if specific dataset not found
            qlib_dir = self.config_path.parent.parent / "data" / "qlib"
            
        qlib_dir = qlib_dir.resolve()
        logger.info(f"Initializing Qlib with provider_uri: {qlib_dir}")
        qlib.init(provider_uri=str(qlib_dir))
        
        # Qlib often resets logging, so we re-setup to ensure our handlers are active
        from utils.logging_config import setup_logging
        setup_logging(skip_rotation=True)
        logger.info("Logging restored after Qlib init.")

    async def run_once(self):
        """Execute one cycle of the trading loop"""
        logger.info(">>> Starting Live Cycle <<<")
        try:
            # 1. Sync Market Prices
            logger.info("Syncing Market Prices...")
            symbols = list(self.strategy.instrument_config.keys())
            if not symbols:
                symbols = self.config.get("data", {}).get("symbols", ["BTC/USDT"])
                
            current_prices = self.exchange.get_latest_prices(symbols)
            self.oms.sync_market_prices(current_prices)
            logger.info(f"Current Prices Sync: {current_prices}")

            # 2. Get Features & Predict
            logger.info("Generating Model Predictions...")
            scores = await self._get_real_scores(symbols)
            
            if scores is None or scores.empty:
                logger.warning("No scores generated. Skipping rebalance.")
                return

            # 3. Detect Regime
            # For now, use forced BULL or implement detector.detect(recent_ohlcv)
            self.strategy.force_regime = MarketRegime.BULL
            
            # 4. Generate Target Weights
            class MockQlibPos:
                def get_stock_list(self): return []
                
            target_weights = self.strategy.generate_target_weight_position(
                scores, 
                MockQlibPos(), 
                pd.Timestamp.now(), 
                pd.Timestamp.now()
            )
            logger.info(f"Target Weights: {target_weights}")

            # 5. Execute Rebalance
            self.oms.execute_rebalance(target_weights, current_prices)
            
            logger.info(">>> Cycle Complete <<<")
        except Exception as e:
            logger.error(f"Error in Live Cycle: {e}", exc_info=True)

    async def _get_real_scores(self, symbols: List[str]) -> Optional[pd.Series]:
        """Fetch features from Qlib and run inference"""
        try:
            # Load feature config
            feature_cfg_file = self.config_path.parent / "features" / f"{self.feature_set}.json"
            if not feature_cfg_file.exists():
                # Fallback to main config dir
                feature_cfg_file = Path(__file__).parent.parent.parent / "config" / "features" / f"{self.feature_set}.json"
            
            if not feature_cfg_file.exists():
                logger.error(f"Feature config not found in any expected location: {feature_cfg_file}")
                return None

            with open(feature_cfg_file, "r") as f:
                handler_config = json.load(f)["config"]
            
            # Clean symbols for Qlib (Exchange format 'BTC/USDT' -> Qlib format 'BTC')
            qlib_symbols = [s.split('/')[0] for s in symbols]
            handler_config["kwargs"]["instruments"] = qlib_symbols
            handler_config["kwargs"]["freq"] = "60min"
            
            # Time range for latest features
            now = datetime.utcnow()
            # Align to hour and shift back 1 to be safe (ensure data is available)
            end_time = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            start_time = end_time - timedelta(hours=200) # Sufficient lookback for Alpha158 features
            
            # Set times in handler config to avoid AssertionError
            start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            handler_config["kwargs"]["start_time"] = start_str
            handler_config["kwargs"]["end_time"] = end_str
            handler_config["kwargs"]["fit_start_time"] = start_str
            handler_config["kwargs"]["fit_end_time"] = end_str
            
            # Remove label for live prediction to avoid missing future data errors
            # But we need at least one field if Qlib checks for it, so we use a dummy that exists
            if "label" in handler_config["kwargs"]:
                handler_config["kwargs"]["label"] = ["$close"] 
            if "learn_processors" in handler_config["kwargs"]:
                handler_config["kwargs"]["learn_processors"] = []
            
            dataset_config = {
                "class": "DatasetH",
                "module_path": "qlib.data.dataset",
                "kwargs": {
                    "handler": handler_config,
                    "segments": {
                        "test": (start_str, end_str)
                    },
                },
            }
            
            dataset = init_instance_by_config(dataset_config)
            all_scores = self.predictor.predict(dataset)
            
            if all_scores.empty:
                logger.warning("Predictor returned empty scores.")
                return None
                
            # Take the latest score for each symbol
            # Index is (datetime, symbol)
            latest_dt = all_scores.index.get_level_values(0).max()
            latest_scores = all_scores.loc[latest_dt]
            
            # Map back to original symbols (Qlib 'BTC' -> Exchange 'BTC/USDT')
            # Create a reverse mapping
            rev_map = {s.split('/')[0]: s for s in symbols}
            latest_scores.index = latest_scores.index.map(lambda x: rev_map.get(x, x))
            
            logger.info(f"Generated real scores for {len(latest_scores)} symbols at {latest_dt}")
            return latest_scores
            
        except Exception as e:
            logger.error(f"Failed to generate real scores: {e}", exc_info=True)
            return None

    async def run_forever(self, interval: int = 3600):
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
    loop = LiveTradingLoop()
    asyncio.run(loop.run_once())
