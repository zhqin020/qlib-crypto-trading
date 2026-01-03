"""
Custom strategies for Qlib backtesting
"""
from typing import Dict, Any, Optional, List, Union
import pandas as pd
import numpy as np
import logging
import copy
from qlib.contrib.strategy.signal_strategy import WeightStrategyBase
from qlib.backtest.decision import TradeDecisionWO, Order, OrderDir
from qlib.backtest.position import Position

logger = logging.getLogger(__name__)

from regime.detector import MarketRegimeDetector, MarketRegime

class CryptoLongShortStrategy(WeightStrategyBase):
    """
    Enhanced Weight-based Strategy for Crypto with Regime Detection.
    """

    def __init__(
        self,
        signal: Any,
        topk: int = 5,
        direction: str = "long",
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        signal_threshold: float = 0.0,
        risk_degree: float = 1.0,
        benchmark: str = "BTC",
        data_freq: Optional[str] = None,
        **kwargs
    ):
        # Remove arguments that might cause issues if passed to super() and not expected
        self.kwargs = kwargs
        # leverage is stored in kwargs by Qlib config usually, but we might have passed it explicitly.
        # Ensure we don't pass 'leverage' to BaseStrategy if it doesn't accept it.
        # But BaseStrategy generally accepts **kwargs.
        # However, WeightedStrategyBase.__init__ calls super().__init__(**kwargs).
        # The error says: BaseStrategy.__init__() got unexpected keyword 'leverage'.
        # This means BaseStrategy doesn't simply store all kwargs.
        
        # We should pop 'leverage' and 'instrument_config' from kwargs before calling super
        leverage = kwargs.pop('leverage', 1.0)
        inst_config = kwargs.pop('instrument_config', {})
        ranking_mode = kwargs.pop('ranking_mode', 'signal')
        amplitude_window = kwargs.pop('amplitude_window', 24)
        min_sigma_threshold = kwargs.pop('min_sigma_threshold', 0.0)
        enable_regime = kwargs.pop('enable_regime', False)
        
        super().__init__(signal=signal, risk_degree=risk_degree, **kwargs)
        
        # Restore them for our use
        self.kwargs['leverage'] = leverage
        self.instrument_config = inst_config
        self.ranking_mode = ranking_mode
        self.amplitude_window = amplitude_window
        self.min_sigma_threshold = min_sigma_threshold
        self.enable_regime = enable_regime
        self.topk = topk
        self.orig_direction = direction.lower() # Store original config
        self.direction = self.orig_direction
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.signal_threshold = signal_threshold
        self.benchmark = benchmark
        self.force_regime = None # Optional override for live mode
        # Resolved data frequency (e.g. '60min'). If not provided, default to 60min.
        self.data_freq = data_freq or "60min"
        
        # Prediction History for Sigma calculation (Confidence)
        self.prediction_history: Dict[str, List[float]] = {}
        self.max_history = 100 # Lookback for sigma logic
        
        # Statistics tracking for adaptive threshold
        self.filtered_signals_count = 0
        self.total_signals_count = 0
        
        # Initialize Regime Detector
        self.detector = MarketRegimeDetector()
        self.entry_info = {} 

        # Instrument-specific configuration
        self.instrument_config = kwargs.get("instrument_config", {})

    def _get_param(self, instrument: str, param: str, default: Any) -> Any:
        """Get parameter for a specific instrument, falling back to default/global."""
        if instrument in self.instrument_config:
            return self.instrument_config[instrument].get(param, default)
        
        # Try simplified name (e.g. BTC for BTC/USDT)
        base_symbol = instrument.split("/")[0] if "/" in instrument else instrument
        if base_symbol in self.instrument_config:
            return self.instrument_config[base_symbol].get(param, default)
            
        return default 

    def generate_target_weight_position(self, score: pd.Series, current: Position, trade_start_time: pd.Timestamp, trade_end_time: pd.Timestamp) -> Dict[str, float]:
        """
        Generate target weights based on predictions and REGIME
        """
        if isinstance(score, pd.DataFrame):
            score = score.iloc[:, 0]
        
        if score is None or score.empty:
            return {}

        # Regime Detection has been disabled as per user request.
        # Original location of lines 109-186
        
        # 1. (Skipped Regime Logic)
        
        # Determine Current Direction (Simplified)
        if self.force_regime:
             logger.warning("Force regime ignored as Regime Detection is disabled.")
        
        current_direction = self.direction


        # 2. Update Entry Prices for new/existing positions
        self._update_entry_info(current)

        # 3. Check for SL/TP hits (Risk Management)
        excl_instruments = self._check_risk_hits(current, trade_start_time, trade_end_time)

        # 4. Filter Excluded Instruments & Normalize Score (Z-Score)
        # Filter out stopped-out instruments first
        if excl_instruments:
            score = score[~score.index.isin(excl_instruments)]
        
        if score.empty:
            return {}

        # Z-Score Normalization (Cross-sectional)
        # This ensures the distribution is centered (mean=0), enabling effective Long-Short
        # and ensuring there represent 'relative' opportunities.
        if len(score) > 1:
            # We skip global Z-score normalization if we want the 'raw' predicted change to be the selector
            # But we keep it as an option. For Per-Symbol modeling, it's better to NOT normalize globally 
            # because different coins have different natural volatility scales.
            pass
        
        # 5. Update Prediction History & Calculate Sigma (Confidence)
        sigmas = {}
        for inst, val in score.items():
            if inst not in self.prediction_history:
                self.prediction_history[inst] = []
            
            # Store history
            self.prediction_history[inst].append(val)
            if len(self.prediction_history[inst]) > self.max_history:
                self.prediction_history[inst].pop(0)
            
            # Calculate Sigma (Z-Score vs itself)
            if len(self.prediction_history[inst]) > 5:
                series = pd.Series(self.prediction_history[inst])
                std = series.std()
                mean = series.mean()
                if std > 1e-6:
                    sigmas[inst] = (val - mean) / std
                else:
                    sigmas[inst] = 0
            else:
                sigmas[inst] = 0

        # 6. Filter by Threshold (on raw prediction if sigma not ready)
        if self.signal_threshold > 0:
            score = score[score.abs() >= self.signal_threshold]
            
        if score.empty:
            return {}

        # 6.5. Adaptive Sigma Threshold Filtering
        self.total_signals_count += len(score)
        
        if self.min_sigma_threshold > 0:
            # Filter signals by confidence (Sigma)
            qualified_signals = {}
            for inst in score.index:
                sigma_val = abs(sigmas.get(inst, 0))
                if sigma_val >= self.min_sigma_threshold:
                    qualified_signals[inst] = score[inst]
            
            filtered_count = len(score) - len(qualified_signals)
            self.filtered_signals_count += filtered_count
            
            if not qualified_signals:
                logger.info(
                    f"⚠️  No signals meet {self.min_sigma_threshold}σ threshold. "
                    f"Filtered {filtered_count}/{len(score)} signals. Holding cash."
                )
                return {}
            
            if filtered_count > 0:
                logger.info(
                    f"🔍 Sigma Filter: {len(qualified_signals)}/{len(score)} signals qualified "
                    f"(threshold: {self.min_sigma_threshold}σ, filtered: {filtered_count})"
                )
            
            # Replace score with qualified signals only
            score = pd.Series(qualified_signals)

        # 7. Selection & Ranking
        # Target: Price magnitude change. Use abs(score) as the primary rank.
        ranking_score = score.abs()
        
        # LOGING SIGMA for observability
        top_ranked = ranking_score.sort_values(ascending=False).head(5)
        for inst in top_ranked.index:
            sigma_val = sigmas.get(inst, 0)
            # Simple probability estimate: how 'extreme' is this signal?
            # Using an approximation of Gaussian CDF for confidence (0.5 to 1.0)
            prob = 0.5 + 0.5 * (1 - np.exp(-0.7 * abs(sigma_val)**2)) # Heuristic CDF
            
            logger.info(f"Signal Track | {inst:10} | Pred: {score[inst]:.4%} | Sigma: {sigma_val:5.2f}σ | Confidence: {prob:.1%}")

        ranking_score = ranking_score.sort_values(ascending=False)
        target_weights = {}
        
        # LOGIC MODIFICATION: Use 'current_direction' instead of self.direction
        
        if current_direction == "long":
            # Long Mode: Only consider positive original scores
            pos_mask = score > 0
            eligible_idx = ranking_score[pos_mask[ranking_score.index]].head(self.topk).index
            
        elif current_direction == "short":
            # Short Mode: Only consider negative original scores
            neg_mask = score < 0
            eligible_idx = ranking_score[neg_mask[ranking_score.index]].head(self.topk).index
            
        elif current_direction == "long-short":
            # Standard Long-Short: Top K by absolute composite score
            eligible_idx = ranking_score.head(self.topk).index

        # Generate weights with leverage
        if len(eligible_idx) > 0:
            # Global leverage default (default to 1.0 if not found)
            global_leverage = self.kwargs.get('leverage', 1.0)
            
            for inst in eligible_idx:
                # Resolve leverage for this asset
                asset_lev = self._get_param(inst, 'leverage', global_leverage)
                
                # Determine Side
                if current_direction == "long-short":
                    side = 1 if score[inst] >= 0 else -1
                elif current_direction == "short":
                    side = -1 
                else: 
                    side = 1
                
                # Weight Calculation
                # Weight = (1 / K) * Leverage * Side
                target_weights[inst] = (1.0 / self.topk) * asset_lev * side
        
        return target_weights

    def _update_entry_info(self, current: Position):
        """Update entry prices for currently held stocks"""
        held_list = current.get_stock_list()
        
        # Remove info for stocks no longer held
        for inst in list(self.entry_info.keys()):
            if inst not in held_list:
                del self.entry_info[inst]
        
        # Add info for new stocks (using current price as entry proxy)
        for inst in held_list:
            if inst not in self.entry_info:
                # In Qlib Position, 'price' is the price at the END of the previous step
                # which is a good proxy for entry price if we just bought it.
                price = current.get_stock_price(inst)
                amount = current.get_stock_amount(inst)
                side = 1 if amount > 0 else -1
                self.entry_info[inst] = {"price": price, "side": side}

    def _check_risk_hits(self, current: Position, start_time: pd.Timestamp, end_time: pd.Timestamp) -> List[str]:
        """Check if any held stock hits Stop Loss or Take Profit"""
        excl = []
        if self.take_profit is None and self.stop_loss is None:
            return excl

        held_list = current.get_stock_list()
        for inst in held_list:
            if inst not in self.entry_info:
                continue
                
            entry_price = self.entry_info[inst]["price"]
            side = self.entry_info[inst]["side"]
            
            # Get current price
            try:
                curr_price = self.trade_exchange.get_close(inst, start_time, end_time)
            except Exception:
                # This could be an indexing outer bounds error (Common in Qlib at data edges)
                continue

            if curr_price is None or np.isnan(curr_price) or entry_price == 0:
                continue

            profit_pct = (curr_price / entry_price - 1.0) * side
            
            # Resolve dynamic params
            sl_threshold = self._get_param(inst, 'stop_loss', self.stop_loss)
            tp_threshold = self._get_param(inst, 'take_profit', self.take_profit)

            # Check SL
            if sl_threshold is not None and profit_pct <= sl_threshold:
                logger.info(f"STOP LOSS hit for {inst}: profit={profit_pct:.2%}, entry={entry_price}, curr={curr_price}, threshold={sl_threshold}")
                excl.append(inst)
            
            # Check TP
            elif tp_threshold is not None and profit_pct >= tp_threshold:
                logger.info(f"TAKE PROFIT hit for {inst}: profit={profit_pct:.2%}, entry={entry_price}, curr={curr_price}, threshold={tp_threshold}")
                excl.append(inst)
                
        return excl

    def _get_amplitudes(self, instruments: List[str], end_time: pd.Timestamp) -> pd.Series:
        # Deprecated: History-based amplitude is less reliable than model prediction
        return pd.Series(1.0, index=instruments)


