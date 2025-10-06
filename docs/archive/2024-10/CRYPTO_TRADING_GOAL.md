# Qlib Crypto Trading Platform - Goal & Implementation

## 🎯 Our Goal

**Build a simple but effective CRYPTO trading model that exceeds other models by tuning it to precision**

### Success Criteria
- **Sharpe Ratio**: >2.0 (excellent), >3.0 (exceptional)
- **Max Drawdown**: <15% (target), <10% (excellent)
- **Information Ratio**: >1.5 (target), >2.0 (excellent)
- **Benchmark**: Outperform buy-and-hold by >50%

### Baseline Benchmarks (Research-Proven)
- Buy-and-hold Sharpe: 1.33
- LSTM Sharpe: 3.23 (research paper)
- GRU Sharpe: 3.12 (research paper)
- LightGBM: Ranked #1 for BTC, ETH, LTC

---

## 🔬 Research-Based Implementation

### Best Models for Crypto (2025 Research)

#### Tier 1 - Proven for Crypto
1. **LightGBM** - Ranked #1 for BTC, ETH, LTC
   - Fast training, handles volatility well
   - Precision-tuned learning rate: 0.03
   - Max depth: 6, Num leaves: 127
   - L1/L2 regularization for regime changes

2. **LSTM** - 3.23 Annualized Sharpe Ratio
   - Best for crypto long-term dependencies
   - 128 hidden units, 3 layers
   - 0.3 dropout for volatile data
   - Early stopping to prevent overtraining

3. **GRU** - 3.12 Sharpe Ratio, #1 for Ripple
   - Efficient temporal pattern recognition
   - Same architecture as LSTM but faster
   - Proven for crypto time series

4. **XGBoost** - Ensemble Boosting
   - 500 trees for robust predictions
   - Subsample 0.8 to reduce overfitting
   - Regularization for regime adaptation

---

## 🏗️ Crypto-Specific Architecture

### 24/7 Trading Calendar
```python
from src.data_pipeline.crypto_calendar_provider import Crypto24x7CalendarProvider
```
- Custom calendar provider for continuous trading
- No market hours or holidays
- Handles crypto's 24/7 nature

### Feature Engineering (Alpha158)
- **158 Technical Features** optimized for crypto:
  - Volatility features (high crypto volatility)
  - Volume features (liquidity analysis)
  - Price features (OHLCV + VWAP)
  - RobustZScoreNorm (clips crypto outliers)

### Data Pipeline
```bash
# Download crypto data
curl -X POST http://localhost:5100/api/data/download \
  -d '{"symbol": "BTC/USDT", "provider": "binance", "interval": "1d", "days": 365}'

# Convert to Qlib format
curl -X POST http://localhost:5100/api/data/convert?dataset=crypto_btc_daily&freq=1d

# Train precision-tuned model
curl -X POST http://localhost:5100/api/models/train \
  -d '{"dataset": "crypto_btc_daily", "model_type": "lightgbm", "feature_set": "alpha158"}'
```

---

## 📊 Precision Tuning Strategy

### LightGBM Crypto Optimization
```json
{
  "learning_rate": 0.03,         // Lower for volatile crypto
  "max_depth": 6,                // Balance complexity
  "num_leaves": 127,             // Capture patterns
  "feature_fraction": 0.8,       // Prevent overfitting
  "lambda_l1": 0.1,              // L1 regularization
  "lambda_l2": 0.2,              // L2 regularization
  "early_stopping_rounds": 50    // Stop before overfit
}
```

### LSTM Crypto Optimization
```json
{
  "hidden_size": 128,            // Temporal dependencies
  "num_layers": 3,               // Deep learning
  "dropout": 0.3,                // High dropout for volatility
  "learning_rate": 0.0005,       // Stable convergence
  "batch_size": 256,             // Memory + gradient stability
  "early_stop": 30               // Prevent overtraining
}
```

---

## 🎛️ Training Configuration

### Data Splits (1096 days of BTC data - 3 years: 2022-2024)
```
Train:  2022-01-01 to 2023-12-31 (2 years / 24 months)
Valid:  2024-01-01 to 2024-06-30 (6 months)
Test:   2024-07-01 to 2024-12-31 (6 months)
```

> **Note:** Last verified 2025-10-07 against `src/models/trainer.py` lines 96-98
> and actual data in `data/raw_full/BTC_USDT_1d.csv` (1097 rows including header)

### Walk-Forward Validation
- Window: 90 days
- Step: 30 days
- Reason: Crypto regimes change frequently

### Transaction Costs (Realistic)
```json
{
  "open_cost": 0.001,    // 0.1% (higher than stocks)
  "close_cost": 0.001,   // 0.1%
  "slippage": 0.0005,    // 0.05%
  "min_cost": 5          // Minimum fee
}
```

---

## 🚀 Running the Precision-Tuned Models

### Quick Start
```bash
# 1. Start the server
cd /Users/chadwyatt/Code/trading/qlib-2
source venv/bin/activate
python -m uvicorn src.ui.api_enhanced:app --host 0.0.0.0 --port 5100

# 2. Train all precision-tuned models
python scripts/train_crypto_models.py

# 3. View results
cat models/training_results.json

# 4. Check logs
tail -f logs/crypto_training.log
```

### Via UI (http://localhost:5100)
1. Navigate to **Models** page
2. Select dataset: `crypto_btc_daily`
3. Select feature set: `Alpha158`
4. Choose model:
   - **LightGBM** (fastest, proven #1)
   - **LSTM** (3.23 Sharpe)
   - **GRU** (3.12 Sharpe)
5. Click **Train Model**

---

## 📈 Validation Metrics

### Qlib Backtest Metrics
```python
{
  "excess_return_without_cost": {
    "mean": float,
    "std": float,
    "annualized_return": float,
    "information_ratio": float,  // Target >1.5
    "max_drawdown": float        // Target <15%
  },
  "excess_return_with_cost": {
    "sharpe_ratio": float,       // Target >2.0
    "sortino_ratio": float,
    "calmar_ratio": float
  }
}
```

### Model Selection Criteria
```python
if sharpe_ratio > 2.0 and max_drawdown < 0.15:
    model_status = "PRODUCTION READY"
elif sharpe_ratio > 1.5 and max_drawdown < 0.20:
    model_status = "GOOD - NEEDS TUNING"
else:
    model_status = "RETRAIN WITH DIFFERENT PARAMS"
```

---

## 🎯 Ensemble Strategy (Production)

### Performance-Weighted Ensemble
```python
{
  "models": [
    "lightgbm_crypto_optimized",
    "lstm_crypto_optimized", 
    "gru_crypto_optimized"
  ],
  "weighting": "Sharpe-weighted",
  "target_sharpe": ">2.5",
  "reason": "Reduces model-specific risk"
}
```

---

## 📊 Current Status

### ✅ Implemented
- [x] 24/7 crypto calendar provider
- [x] CCXT data pipeline (Binance, Kraken, Coinbase)
- [x] Qlib dataset conversion
- [x] Alpha158 feature engineering
- [x] 9 ML models (LightGBM, XGBoost, LSTM, GRU, Transformer, CNN-LSTM, Linear, SVM, KNN)
- [x] Precision-tuned crypto configurations
- [x] Comprehensive testing framework (100% pass rate)
- [x] Professional dark mode UI
- [x] MCP tools for programmatic control
- [x] Real-time WebSocket updates

### 🔄 In Progress
- [ ] Training precision-tuned models
- [ ] Validating Sharpe ratio >2.0
- [ ] Backtesting with realistic costs

### 🎯 Next Steps
1. Complete model training
2. Compare performance vs baseline
3. Select best model (or ensemble)
4. Deploy to production
5. Monitor and retrain weekly

---

## 🏆 Success Metrics

### Goal Achievement
```
IF model.sharpe_ratio > 2.0 AND model.max_drawdown < 0.15:
    ✅ GOAL ACHIEVED - Simple, effective, precision-tuned crypto model
ELSE IF model.sharpe_ratio > buy_and_hold.sharpe * 1.5:
    ✅ EXCEEDS BASELINE - Continue optimization
ELSE:
    ❌ NEEDS TUNING - Adjust hyperparameters
```

### Production Deployment Checklist
- [ ] Sharpe ratio >2.0 achieved
- [ ] Max drawdown <15% achieved  
- [ ] Outperforms buy-and-hold by >50%
- [ ] Consistent across CV folds
- [ ] Transaction costs included
- [ ] Monitoring dashboard active
- [ ] Weekly retraining scheduled

---

## 📚 References

- Microsoft Qlib: https://github.com/microsoft/qlib
- Research: "Comprehensive Analysis of ML Models for Algorithmic Trading of Bitcoin" (arXiv)
- Research: "LightGBM & GRU ranked #1 for crypto" (2025)
- Research: "LSTM 3.23 Sharpe ratio" (ensemble methods paper)

---

**Built with Microsoft Qlib + Crypto-Specific Optimizations**
**Goal: Simple, Effective, Precision-Tuned Crypto Trading**
