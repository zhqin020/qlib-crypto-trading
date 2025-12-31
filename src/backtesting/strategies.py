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

class CryptoLongShortStrategy(WeightStrategyBase):
    """
    Enhanced Weight-based Strategy for Crypto:
    - Supports Direction: long, short, long-short
    - Supports Top-K ranking
    - Supports Risk Control: Take Profit (TP), Stop Loss (SL)
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
        **kwargs
    ):
        super().__init__(signal=signal, risk_degree=risk_degree, **kwargs)
        self.topk = topk
        self.direction = direction.lower()
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.signal_threshold = signal_threshold
        
        # Track entry prices for SL/TP
        # {instrument: {"price": float, "side": int}}
        self.entry_info = {} 

    def generate_target_weight_position(self, score: pd.Series, current: Position, trade_start_time: pd.Timestamp, trade_end_time: pd.Timestamp) -> Dict[str, float]:
        """
        Generate target weights based on predictions and direction
        """
        if isinstance(score, pd.DataFrame):
            score = score.iloc[:, 0]
        
        if score is None or score.empty:
            return {}

        # 1. Update Entry Prices for new/existing positions
        self._update_entry_info(current)

        # 2. Check for SL/TP hits
        # If any position hits SL/TP, we want to close it (set weight to 0)
        # and prevent re-entry in the same bar.
        excl_instruments = self._check_risk_hits(current, trade_start_time, trade_end_time)

        # 3. Filter by signal threshold (Absolute value)
        # If score is below threshold, it's considered noise and ignored
        if self.signal_threshold > 0:
            score = score[score.abs() >= self.signal_threshold]
        
        if score.empty:
            return {}

        # 4. Rank scores
        score = score.sort_values(ascending=False)
        
        target_weights = {}
        
        # 4. Assign weights based on direction
        if self.direction == "long":
            topk_idx = [i for i in score.head(self.topk * 2).index if i not in excl_instruments][:self.topk]
            if topk_idx:
                unit_weight = 1.0 / len(topk_idx)
                for inst in topk_idx:
                    target_weights[inst] = unit_weight
                
        elif self.direction == "short":
            bottomk_idx = [i for i in score.tail(self.topk * 2).index if i not in excl_instruments][:self.topk]
            if bottomk_idx:
                unit_weight = -1.0 / len(bottomk_idx)
                for inst in bottomk_idx:
                    target_weights[inst] = unit_weight
                
        elif self.direction == "long-short":
            # 1. Filter out excluded instruments
            valid_scores = score[~score.index.isin(excl_instruments)]
            
            # 2. Sort by Absolute Value (Confidence)
            # This identifies the instruments the model is MOST SURE about, regardless of direction
            abs_score = valid_scores.abs().sort_values(ascending=False)
            topk_idx = abs_score.head(self.topk).index
            
            if len(topk_idx) > 0:
                # Each selected instrument gets 1/topk share of the total exposure
                unit_weight = 1.0 / self.topk
                for inst in topk_idx:
                    # Direction is determined by the sign of the original prediction
                    side = 1 if valid_scores[inst] >= 0 else -1
                    target_weights[inst] = side * unit_weight
        
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
            
            # Check SL
            if self.stop_loss is not None and profit_pct <= self.stop_loss:
                logger.info(f"STOP LOSS hit for {inst}: profit={profit_pct:.2%}, entry={entry_price}, curr={curr_price}")
                excl.append(inst)
            
            # Check TP
            elif self.take_profit is not None and profit_pct >= self.take_profit:
                logger.info(f"TAKE PROFIT hit for {inst}: profit={profit_pct:.2%}, entry={entry_price}, curr={curr_price}")
                excl.append(inst)
                
        return excl
