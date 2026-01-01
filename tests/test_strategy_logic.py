
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Setup Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Define a proper dummy base class
class DummyWeightStrategyBase:
    def __init__(self, *args, **kwargs):
        self.common_infra = kwargs.get("common_infra", None)
        self.trade_exchange = kwargs.get("trade_exchange", None)

# Mock the module to provide this class
mock_strat_module = MagicMock()
mock_strat_module.WeightStrategyBase = DummyWeightStrategyBase
sys.modules["qlib.contrib.strategy.signal_strategy"] = mock_strat_module

sys.modules["qlib.backtest.decision"] = MagicMock()
sys.modules["qlib.backtest.position"] = MagicMock()

# Mock qlib.data but allow D to be configured
mock_data = MagicMock()
sys.modules["qlib.data"] = mock_data

# Import
from backtesting.strategies import CryptoLongShortStrategy
from regime.detector import MarketRegime

class TestCryptoLongShortStrategy(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        mock_data.reset_mock()
        
        self.config = {
            "topk": 2,
            "direction": "long-short",
            "leverage": 1.0,
            "signal_threshold": 0.5,
            "instrument_config": {
                "BTC/USDT": {"leverage": 2.0, "stop_loss": -0.05},
                "PEPE/USDT": {"leverage": 1.0, "stop_loss": -0.10},
            }
        }
        
    def setUp(self):
        # Reset mocks
        mock_data.reset_mock()
        
        self.config = {
            "topk": 2,
            "direction": "long-short",
            "leverage": 1.0,
            "signal_threshold": 0.5,
            "instrument_config": {
                "BTC/USDT": {"leverage": 2.0, "stop_loss": -0.05},
                "PEPE/USDT": {"leverage": 1.0, "stop_loss": -0.10},
            }
        }
        
        # Instantiate directly 
        self.strategy = CryptoLongShortStrategy(signal=pd.DataFrame(), **self.config)
        self.strategy.kwargs = self.config # Ensure kwargs are set if base doesn't do it
        
        # Mock Detector
        self.strategy.detector = MagicMock()
        # Default behavior: Returns SIDEWAYS
        # Include 'price' in metrics to avoid formatting error in logs
        self.strategy.detector.detect.return_value = (MarketRegime.SIDEWAYS, 0.0, {"price": 100.0})
        
        # Mock Exchange
        self.strategy.trade_exchange = MagicMock()

        # Mock D.features to return a valid DataFrame so logic proceeds to detect()
        # Create a dummy DF that is NOT empty
        dummy_df = pd.DataFrame({"close": [100, 101]}, index=[0, 1])
        mock_data.D.features.return_value = dummy_df
        
        # We also need to mock D.features raising/handling or ensure it returns properly
        # The code does:
        # if not btc_df.empty: ...
        # If D.features returns a Mock, .empty is a Mock.
        # We need .empty to be False.
        # Because we return a real DF, .empty is False. Correct.

    def test_z_score_normalization(self):
        """Test if scores are normalized correctly"""
        scores = pd.Series({
            "BTC/USDT": 12.0,
            "ETH/USDT": 10.0,
            "SOL/USDT": 8.0,
            "PEPE/USDT": 14.0
        })
        
        mock_position = MagicMock()
        mock_position.get_stock_list.return_value = []
        
        # Ensure D.features works
        # Run
        weights = self.strategy.generate_target_weight_position(
            scores, mock_position, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")
        )
        
        # Norm Scores approx:
        # Mean=11.0, Std=2.58
        # BTC (12): +0.38 (Excluded < 0.5)
        # ETH (10): -0.38 (Excluded > -0.5)
        # SOL (8): -1.16 (Short)
        # PEPE (14): +1.16 (Long)
        
        # Expected: PEPE and SOL
        self.assertIn("PEPE/USDT", weights)
        self.assertIn("SOL/USDT", weights)
        self.assertNotIn("ETH/USDT", weights) 
        self.assertNotIn("BTC/USDT", weights)
        
        self.assertGreater(weights["PEPE/USDT"], 0)
        self.assertLess(weights["SOL/USDT"], 0)

    def test_instrument_leverage(self):
        """Test per-instrument leverage"""
        self.strategy.signal_threshold = 0.1
        self.strategy.direction = "long" # Force Long (will be overridden by logic if Regime is detected as something else)
        
        # We force Regime = BULL so standard logic doesn't override direction to short
        self.strategy.detector.detect.return_value = (MarketRegime.BULL, 1.0, {"price": 100.0})
        
        scores = pd.Series({
            "BTC/USDT": 10.0,
            "PEPE/USDT": 9.0,
            "ETH/USDT": 0.0,
            "SOL/USDT": 0.0
        })
        
        mock_position = MagicMock()
        mock_position.get_stock_list.return_value = []

        weights = self.strategy.generate_target_weight_position(
            scores, mock_position, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")
        )
        
        # Top 2: BTC, PEPE
        # Weights:
        # BTC: 0.5 * 2.0 = 1.0
        # PEPE: 0.5 * 1.0 = 0.5
        
        self.assertAlmostEqual(weights.get("BTC/USDT", 0), 1.0)
        self.assertAlmostEqual(weights.get("PEPE/USDT", 0), 0.5)

    def test_strict_short_logic(self):
        """Test Short Logic Strictness"""
        # Regime BEAR
        self.strategy.detector.detect.return_value = (MarketRegime.BEAR, -1.0, {"price": 100.0})
        
        self.strategy.signal_threshold = 1.5
        
        # Scores centered around 10
        scores = pd.Series({
             "A": 11.0, 
             "B": 9.0,  
             "C": 12.0, 
             "D": 8.0 
        })
        # Z-scores small (< 2.0)
        
        mock_position = MagicMock()
        mock_position.get_stock_list.return_value = []
        
        weights = self.strategy.generate_target_weight_position(
            scores, mock_position, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")
        )
        
        # Expect Empty
        self.assertEqual(len(weights), 0)
        
        # Add strong negative signal
        scores["E"] = 0.0 # Creates Z << -1.0
        weights_2 = self.strategy.generate_target_weight_position(
            scores, mock_position, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")
        )
        self.assertIn("E", weights_2)
        self.assertLess(weights_2["E"], 0)

    def test_get_param(self):
        """Test parameter execution"""
        # Now without the extra patch, this should work
        self.assertEqual(self.strategy._get_param("BTC/USDT", "leverage", 99), 2.0)
        self.assertEqual(self.strategy._get_param("PEPE/USDT", "stop_loss", -1), -0.10)
        self.assertEqual(self.strategy._get_param("ETH/USDT", "leverage", 5.0), 5.0)

if __name__ == "__main__":
    unittest.main()
