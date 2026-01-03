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
🚀 下一步方向建议
基于目前的进展，我建议从以下三个维度中选择一个作为下一步的突破口：

方向 1：自适应 Sigma 阈值决策 (Adaptive Execution)
设想：目前我们是取固定数量的 $TopK$ 币种。
目标：改为基于 置信度门槛。例如：只有当某个信号的置信度 $> 90%$（或 $Sigma > 2.5$）时才允许开仓。
价值：宁缺毋滥，在震荡市中自动过滤那些低置信度的日常噪音信号。
方向 2：单币种特征专家分析 (Instrument-Specific Meta-Analysis)
设想：每个币种的模型现在是独立的，但它们共享相同的 158 个因子。
目标：分析并筛选出对 BTC 特别有效的因子，与对 SOL 特别有效的因子。
价值：为不同属性的币种量身定制“特征工程”，进一步提升单币种模型的 F1-Score。
方向 3：深度学习原生置信度 (Uncertainty Quantification)
设想：目前 Sigma 是基于统计结果的外部评价。
目标：在推理时启用 MC Dropout，让 ALSTM 运行 10 次并计算方差，得出模型内部的“不确定性”。
价值：如果 10 次运行结果一致，说明模型对当前走势“非常有把握”，这比单纯的偏离度统计更具前瞻性。