#!/usr/bin/env python3
"""
GOAL: Build a SIMPLE but EFFECTIVE CRYPTO trading model
Target: Sharpe ratio >2.0, Max Drawdown <15%

Using direct CSV data + proven models (LightGBM, LSTM, GRU)
Based on 2025 research showing these models achieve 3.23 Sharpe for crypto
"""
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import RobustScaler
import lightgbm as lgb
import json
from datetime import datetime

print("="*80)
print("SIMPLE EFFECTIVE CRYPTO TRADING MODEL")
print("Goal: Sharpe >2.0, Max Drawdown <15%")
print("="*80)

# Load crypto data
data_file = Path("/Users/chadwyatt/Code/trading/qlib-2/data/raw/BTC_USDT_1d.csv")
df = pd.read_csv(data_file)
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)

print(f"\nData loaded: {len(df)} days (2024-01-01 to 2024-12-31)")
print(f"Columns: {list(df.columns)}")

# Create crypto-specific features (simple but effective)
def create_features(df):
    """Create proven crypto features"""
    df = df.copy()

    # Price features
    df['returns'] = df['close'].pct_change()
    df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

    # Volatility (critical for crypto)
    df['volatility_5'] = df['returns'].rolling(5).std()
    df['volatility_20'] = df['returns'].rolling(20).std()

    # Moving averages
    for period in [5, 10, 20, 50]:
        df[f'sma_{period}'] = df['close'].rolling(period).mean()
        df[f'price_to_sma_{period}'] = df['close'] / df[f'sma_{period}']

    # Volume features
    df['volume_sma_5'] = df['volume'].rolling(5).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma_5']

    # High-low range (volatility proxy)
    df['hl_ratio'] = (df['high'] - df['low']) / df['close']

    # Momentum
    for period in [5, 10, 20]:
        df[f'momentum_{period}'] = df['close'] / df['close'].shift(period) - 1

    # Target: Next day return
    df['target'] = df['close'].shift(-1) / df['close'] - 1

    return df

df = create_features(df)
df = df.dropna()

print(f"\nFeatures created: {len([c for c in df.columns if c != 'target'])} features")
print(f"Valid samples after dropna: {len(df)}")

# Split data (time series split)
train_size = int(len(df) * 0.7)  # 70% train
valid_size = int(len(df) * 0.15)  # 15% valid
test_size = len(df) - train_size - valid_size  # 15% test

train_df = df.iloc[:train_size]
valid_df = df.iloc[train_size:train_size+valid_size]
test_df = df.iloc[train_size+valid_size:]

print(f"\nTrain: {len(train_df)} days ({train_df.index.min().date()} to {train_df.index.max().date()})")
print(f"Valid: {len(valid_df)} days ({valid_df.index.min().date()} to {valid_df.index.max().date()})")
print(f"Test:  {len(test_df)} days ({test_df.index.min().date()} to {test_df.index.max().date()})")

# Prepare features and target
feature_cols = [c for c in df.columns if c not in ['target', 'timestamp']]
X_train = train_df[feature_cols]
y_train = train_df['target']
X_valid = valid_df[feature_cols]
y_valid = valid_df['target']
X_test = test_df[feature_cols]
y_test = test_df['target']

# Normalize (robust to outliers - critical for crypto)
scaler = RobustScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_valid_scaled = scaler.transform(X_valid)
X_test_scaled = scaler.transform(X_test)

print(f"\n" + "="*80)
print("TRAINING LIGHTGBM (Research-proven #1 for BTC)")
print("="*80)

# Precision-tuned LightGBM for crypto
lgb_params = {
    'objective': 'regression',
    'metric': 'rmse',
    'boosting_type': 'gbdt',
    'learning_rate': 0.03,
    'num_leaves': 127,
    'max_depth': 6,
    'min_data_in_leaf': 20,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'lambda_l1': 0.1,
    'lambda_l2': 0.2,
    'verbose': -1
}

train_data = lgb.Dataset(X_train_scaled, label=y_train)
valid_data = lgb.Dataset(X_valid_scaled, label=y_valid, reference=train_data)

model = lgb.train(
    lgb_params,
    train_data,
    num_boost_round=1000,
    valid_sets=[train_data, valid_data],
    valid_names=['train', 'valid'],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
)

print(f"\n✅ Model trained! Best iteration: {model.best_iteration}")

# Make predictions
train_pred = model.predict(X_train_scaled)
valid_pred = model.predict(X_valid_scaled)
test_pred = model.predict(X_test_scaled)

# Calculate metrics
def calculate_sharpe(returns, rf_rate=0.0):
    """Calculate Sharpe ratio"""
    excess_returns = returns - rf_rate
    if excess_returns.std() == 0:
        return 0
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()

def calculate_max_drawdown(returns):
    """Calculate maximum drawdown"""
    cum_returns = (1 + returns).cumprod()
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    return drawdown.min()

# Strategy: Long top 30% predictions, Short bottom 30%
n_long = int(len(test_pred) * 0.3)
test_signals = pd.Series(0, index=y_test.index)
sorted_idx = pd.Series(test_pred, index=y_test.index).sort_values(ascending=False)
test_signals.loc[sorted_idx.index[:n_long]] = 1  # Long top 30%
test_signals.loc[sorted_idx.index[-n_long:]] = -1  # Short bottom 30%
test_strategy_returns = y_test * test_signals

print(f"\n" + "="*80)
print("BACKTEST RESULTS (Out-of-Sample)")
print("="*80)

# Buy and hold benchmark
buy_hold_returns = y_test
buy_hold_sharpe = calculate_sharpe(buy_hold_returns)
buy_hold_mdd = calculate_max_drawdown(buy_hold_returns)
buy_hold_total_return = (1 + buy_hold_returns).prod() - 1

# Strategy metrics
strategy_sharpe = calculate_sharpe(test_strategy_returns)
strategy_mdd = calculate_max_drawdown(test_strategy_returns)
strategy_total_return = (1 + test_strategy_returns).prod() - 1

# Transaction costs (0.1% per trade)
n_trades = test_signals.diff().abs().sum()
transaction_costs = n_trades * 0.001
strategy_total_return_with_cost = strategy_total_return - transaction_costs

print(f"\n📊 Buy & Hold (Benchmark):")
print(f"   Total Return: {buy_hold_total_return*100:.2f}%")
print(f"   Sharpe Ratio: {buy_hold_sharpe:.3f}")
print(f"   Max Drawdown: {buy_hold_mdd*100:.2f}%")

print(f"\n🚀 LightGBM Strategy:")
print(f"   Total Return: {strategy_total_return*100:.2f}%")
print(f"   Return (after costs): {strategy_total_return_with_cost*100:.2f}%")
print(f"   Sharpe Ratio: {strategy_sharpe:.3f}")
print(f"   Max Drawdown: {strategy_mdd*100:.2f}%")
print(f"   Number of Trades: {int(n_trades)}")

print(f"\n🎯 GOAL ASSESSMENT:")
target_sharpe = 2.0
target_mdd = -0.15

if strategy_sharpe > target_sharpe and strategy_mdd > target_mdd:
    print(f"   ✅ GOAL ACHIEVED!")
    print(f"   ✅ Sharpe {strategy_sharpe:.3f} > {target_sharpe} ✓")
    print(f"   ✅ MaxDD {strategy_mdd*100:.2f}% > {target_mdd*100}% ✓")
    status = "PRODUCTION_READY"
elif strategy_sharpe > buy_hold_sharpe * 1.5:
    print(f"   ⚠️  EXCEEDS BASELINE (needs tuning)")
    print(f"   Sharpe {strategy_sharpe:.3f} vs Buy-Hold {buy_hold_sharpe:.3f}")
    print(f"   Improvement: {(strategy_sharpe/buy_hold_sharpe - 1)*100:.1f}%")
    status = "GOOD_NEEDS_TUNING"
else:
    print(f"   ❌ NEEDS RETRAINING")
    print(f"   Sharpe {strategy_sharpe:.3f} < Target {target_sharpe}")
    status = "RETRAIN_NEEDED"

# Save results
results = {
    "timestamp": datetime.now().isoformat(),
    "model": "LightGBM_Crypto_Optimized",
    "goal": "Simple effective crypto model - Sharpe >2.0, MaxDD <15%",
    "data": {
        "train_days": len(train_df),
        "valid_days": len(valid_df),
        "test_days": len(test_df),
        "features": len(feature_cols)
    },
    "performance": {
        "buy_hold_sharpe": float(buy_hold_sharpe),
        "buy_hold_return": float(buy_hold_total_return),
        "buy_hold_mdd": float(buy_hold_mdd),
        "strategy_sharpe": float(strategy_sharpe),
        "strategy_return": float(strategy_total_return),
        "strategy_return_after_costs": float(strategy_total_return_with_cost),
        "strategy_mdd": float(strategy_mdd),
        "trades": int(n_trades),
        "improvement_vs_baseline": float(strategy_sharpe / buy_hold_sharpe - 1)
    },
    "status": status,
    "goal_achieved": bool(strategy_sharpe > target_sharpe and strategy_mdd > target_mdd)
}

results_file = Path("/Users/chadwyatt/Code/trading/qlib-2/models/simple_crypto_model_results.json")
with open(results_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n📁 Results saved to: {results_file}")
print("="*80)
