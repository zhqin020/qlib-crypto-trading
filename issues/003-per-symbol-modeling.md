# ISSUE-003: Per-Symbol Modeling Integration

**Status**: CLOSED
**Priority**: HIGH
**Created**: 2026-01-02
**Last Updated**: 2026-01-02

## 📋 Description
Shift from Global Modeling to Per-Symbol Modeling. Each instrument in the universe has its own optimized ALSTM model. The selection logic prioritizes "Predictive Magnitude" (expected price change) and "Statistical Confidence" (Sigma) over lagging indicators like historical amplitude.

## ✅ Accomplishments
- [x] **Per-Instrument Training**: Created `scripts/train_per_symbol.py` to automate training specialized models for each asset.
- [x] **Multi-Model Predictor**: Upgraded `QlibPredictor` to support JSON-based model mapping and high-efficiency per-symbol inference via `SubsetDatasetWrapper`.
- [x] **Signal Confidence Modeling**: Implemented `Signal Sigma` logic to track predictability and confidence for each individual model.
- [x] **Elimination of Deceptive Indicators**: Removed historical amplitude weighting in favor of pure model-driven expected return ranking.

## 🛠 Refined Ranking Logic (v2)
- **Primary Rank**: `Score = abs(Predicted_Return_1h)`. We trust the model to identify the largest upcoming price moves.
- **Confidence Metric (Sigma)**: 
    - Each symbol maintains a rolling buffer of its own predictions.
    - `Sigma = (Current_Pred - Rolling_Mean) / Rolling_Std`.
    - High Sigma indicates a "Strong Consensus" from the model's internal feature recognition, distinguishing significant signals from background noise.
- **Confidence %**: A heuristic mapping of Sigma to a [50%, 100%] scale for intuitive monitoring.

## 🚀 Technical Execution
1.  **Core Trainer**: Modified `src/models/trainer.py` to support instrument-specific data narrowing.
2.  **Inference Dispatcher**: Refactored `src/serving/predictor.py` to handle N models simultaneously without data reloading penalties.
3.  **Strategy Engine**: Updated `src/backtesting/strategies.py` with:
    - Prediction history buffers.
    - Automatic Sigma/Confidence calculation.
    - Pure magnitude ranking.

## 📊 Verification Results
- **Dynamic Selection**: Confirmed via `logs/qlib-crypto-1.log` that the strategy correctly ranks BTC and ETH based on predicted return magnitude.
- **Observability**: Added "Signal Track" log entries showing: `Instrument | Pred % | Sigma | Confidence %`.
- **End-to-End**: Verified that the OMS executes trades based on these refined, high-confidence signals.

## 💡 Future Directions
1.  **Adaptive Sigma-Thresholding**: Instead of trading the `TopK` fixed assets, only execute trades where `Confidence > 90%`.
2.  **Per-Symbol Meta-Optimization**: Analyze which of the 158 features contribute most to each coin's performance to further refine individual models.
3.  **Uncertainty Quantification**: Implement MC Dropout in `QlibPredictor` for deep-learning-native confidence estimation.
