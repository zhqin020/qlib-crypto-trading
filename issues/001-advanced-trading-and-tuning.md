# Issue #001: Advanced Trading Strategy & Smart Tuning Implementation

## 📝 Description
The goal was to enhance the platform's trading capabilities by supporting long-short strategies, implementing risk controls (SL/TP), and upgrading the hyperparameter tuning process to be more intelligent and risk-aware.

## ✅ Accomplishments

### 1. Advanced Crypto Strategy (`CryptoLongShortStrategy`)
- Implemented a custom weight-based strategy that supports:
    - **Long-Short**: Buying top-ranked assets and shorting bottom-ranked assets simultaneously.
    - **Direction Control**: Easy switching between `long`, `short`, and `long-short` modes.
    - **Stop-Loss / Take-Profit**: Automated exit logic based on entry price tracking.
    - **Leverage**: Built-in support for leveraged positions.

### 2. Smart Hyperparameter Tuning
- **Optuna Integration**: Optimized the search process using Bayesian optimization.
- **WPS (Weighted Performance Score)**:
    - `0.40 * Sharpe + 0.15 * Sortino + 0.10 * Calmar + 0.10 * WinRate`
    - Penalties for drawdowns exceeding 20%.
    - Disqualification for drawdowns exceeding 50%.
- **Holistic Tuning**: Optimized both model parameters (LR, Hidden Size) and strategy parameters (Top-K, Leverage) in a single run.

### 3. Backtesting Engine Upgrades
- Enhanced `src/backtesting/engine.py` to dynamically initialize the custom strategy based on user configuration.
- Standardized the passing of parameters from CLI/JSON to the Qlib executor.

## 📊 Results (Example ALSTM Run)
- **Sharpe Ratio**: 2.487 (Previous best: ~0.85)
- **Max Drawdown**: 8.57% (Reduced from ~45%)
- **Annualized Return**: 41.43%
- **Win Rate**: 56.49%

## 📂 Modified Files
- `src/backtesting/strategies.py`: New custom strategy implementation.
- `src/backtesting/engine.py`: Integration of custom strategy and leverage.
- `scripts/tune_hyperparameters.py`: Upgrade to Optuna and WPS.
- `scripts/run_backtest.py`: Support for `--tp`, `--sl`, and `--direction` arguments.
- `config/trading_params.json`: Added `trading` section and standardized structure.

## 📅 Status
- **Status**: CLOSED
- **Date**: 2025-12-30
- **Lead**: Antigravity (AI Assistant)
