import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple, List
from enum import Enum

class MarketRegime(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"

class MarketRegimeDetector:
    """
    Detects market regime (Trend + Volatility + Momentum)
    Based on BTC/USDT technical indicators.
    """
    
    def __init__(self, ema_short=20, ema_long=60, rsi_period=14, rsi_threshold=50, vol_window=20):
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.rsi_period = rsi_period
        self.rsi_threshold = rsi_threshold
        self.vol_window = vol_window
        self.logger = logging.getLogger(__name__)

    def detect(self, df: pd.DataFrame) -> Tuple[MarketRegime, float, Dict]:
        """
        Detect regime for a single day based on historical data up to that day.
        
        Args:
            df: DataFrame with OHLCV data (Must contain '$close' or 'close')
                Index should be datetime.
        
        Returns:
            (MarketRegime, RiskScore, MetricsDict)
            RiskScore: 0.0 (Max Risk/Bear) to 1.0 (Min Risk/Bull)
        """
        if df.empty or len(df) < self.ema_long + 1:
            return MarketRegime.UNKNOWN, 0.5, {}

        # Ensure column standard
        close_col = '$close' if '$close' in df.columns else 'close'
        if close_col not in df.columns:
             # Try to find a plausible close column
             for c in df.columns:
                 if 'close' in c.lower():
                     close_col = c
                     break
        
        prices = df[close_col]
        
        # Calculate Indicators
        # 1. EMA
        ema_s = prices.ewm(span=self.ema_short, adjust=False).mean()
        ema_l = prices.ewm(span=self.ema_long, adjust=False).mean()
        
        # 2. RSI
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 3. Volatility (ATR-like or StdDev)
        # Simple rolling std dev of returns
        returns = prices.pct_change()
        vol = returns.rolling(window=self.vol_window).std()
        
        # Get latest values
        curr_price = prices.iloc[-1]
        curr_ema_s = ema_s.iloc[-1]
        curr_ema_l = ema_l.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_vol = vol.iloc[-1]
        
        # Logic
        # Score System: -2 to +2
        score = 0
        
        # Trend Score
        if curr_price > curr_ema_l:
            score += 1
            if curr_ema_s > curr_ema_l:
                score += 0.5
        else:
            score -= 1
            if curr_ema_s < curr_ema_l:
                score -= 0.5
                
        # Momentum Score
        if curr_rsi > 60:
            score += 0.5
        elif curr_rsi < 40:
            score -= 0.5
            
        # Volatility Filter (High vol in downtrend is extra bearish)
        # We define "High Vol" as > 90th percentile of recent history? 
        # For simplicity, we just check absolute magnitude if available, 
        # but relative is better.
        # Let's say if recent vol is 1.5x of average vol
        avg_vol = vol.iloc[-self.vol_window*5:].mean()
        is_high_vol = curr_vol > (avg_vol * 1.3)
        
        if score < 0 and is_high_vol:
            # Panic selling
            score -= 0.5
            
        # Determine Regime
        if score >= 1.0:
            regime = MarketRegime.BULL
        elif score <= -1.0:
            regime = MarketRegime.BEAR
        else:
            regime = MarketRegime.SIDEWAYS
            
        # Map Score to Risk Factor (for strategy sizing)
        # Bear (-2.5) -> 0.0
        # Bull (+2.0) -> 1.0
        # Sideways -> 0.5
        
        # Normalize score -2.5 to 2.0 to 0.0-1.0
        norm_score = (score + 2.5) / 4.5
        risk_score = max(0.0, min(1.0, norm_score))
        
        metrics = {
            "score": score,
            "rsi": curr_rsi,
            "ema_gap": (curr_ema_s - curr_ema_l) / curr_ema_l,
            "volatility": curr_vol,
            "price": curr_price
        }
        
        return regime, risk_score, metrics
