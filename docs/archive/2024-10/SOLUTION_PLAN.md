# Solution Plan: Achieve Crypto Trading Goal

## 🎯 Goal Reminder
**Build a SIMPLE but EFFECTIVE CRYPTO trading model that exceeds other models**
- Target: Sharpe Ratio >2.0, Max Drawdown <15%
- Current: Sharpe -0.250 (NEEDS FIX)

---

## 📋 Outstanding Problems

### Problem 1: Qlib Data Loading Broken ⚠️ CRITICAL
**Symptom**: `D.features()` returns empty dataframe despite binary files existing
**Impact**: Can't use Qlib's proven models with Alpha158 features
**Priority**: HIGH - Blocks entire Qlib workflow

### Problem 2: Training Data Configuration 📊
**Current**: 1096 days (3 years: 2022-2024) available
**Status**: Sufficient data for stable training
**Priority**: ✅ RESOLVED - 3 years of data now available

> **Verified:** 2025-10-07 - `data/raw_full/BTC_USDT_1d.csv` contains 1096 days

### Problem 3: Model Performance ❌
**Current**: Negative Sharpe (-0.250)
**Target**: Sharpe >2.0
**Priority**: MEDIUM - Will improve with fixes above

---

## 🔧 Solution Plan (3 Parallel Tracks)

### Track 1: Fix Qlib Data Loading (2-3 hours)
**Goal**: Get Qlib to read our crypto data properly

#### Step 1.1: Debug Qlib Data Format (30 min)
```bash
# Test 1: Check if Qlib can read any sample data
cd /tmp
git clone https://github.com/microsoft/qlib.git
python qlib/scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# Test 2: Compare working data structure with ours
ls -la ~/.qlib/qlib_data/cn_data/instruments/
ls -la /Users/chadwyatt/Code/trading/qlib-2/data/qlib/crypto_btc_daily/instruments/

# Test 3: Compare binary file formats
hexdump -C ~/.qlib/qlib_data/cn_data/features/*/close.bin | head -20
hexdump -C /Users/chadwyatt/Code/trading/qlib-2/data/qlib/crypto_btc_daily/features/BTC/close.bin | head -20
```

**Expected Outcome**: Identify format mismatch

#### Step 1.2: Use Qlib's Official Data Conversion (1 hour)
```bash
# Option A: Use Qlib's dump_bin.py (recommended)
cd /Users/chadwyatt/Code/trading/qlib-2

# Create conversion script using Qlib's official tools
python scripts/qlib_official_converter.py \
  --csv_path data/raw/BTC_USDT_1d.csv \
  --qlib_dir data/qlib/crypto_official \
  --freq day \
  --date_field_name datetime

# Option B: Use DumpDataAll from Qlib
from qlib.data import D
from qlib.contrib.data.handler import DumpDataAll

# Dump our CSV to Qlib format
dumper = DumpDataAll(
    csv_path="data/raw/BTC_USDT_1d.csv",
    qlib_dir="data/qlib/crypto_official",
    freq="day",
    include_fields="open,close,high,low,volume",
    date_field_name="datetime"
)
dumper.dump()
```

**Expected Outcome**: Working Qlib dataset

#### Step 1.3: Validate Data Loading (30 min)
```python
import qlib
from qlib.data import D

# Test loading
qlib.init(provider_uri={'day': 'data/qlib/crypto_official'})
df = D.features(['BTC'], ['$close', '$open'], 
                start_time='2024-01-01', end_time='2024-12-31')

print(f"✅ SUCCESS: {len(df)} rows loaded" if len(df) > 0 else "❌ FAILED")
```

**Success Criteria**: `len(df) > 300`

---

### Track 2: Download More Data (1-2 hours)
**Goal**: Get 3 years of data (2022-2024) for multiple cryptos

#### Step 2.1: Download Historical Data (30 min)
```bash
# Use our existing API to download more data
curl -X POST http://localhost:5100/api/data/download \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "provider": "binance",
    "interval": "1d",
    "start_date": "2022-01-01",
    "end_date": "2024-12-31"
  }'

# Download additional symbols
for symbol in ETH/USDT SOL/USDT; do
  curl -X POST http://localhost:5100/api/data/download \
    -H "Content-Type: application/json" \
    -d "{
      \"symbol\": \"$symbol\",
      \"provider\": \"binance\",
      \"interval\": \"1d\",
      \"start_date\": \"2022-01-01\",
      \"end_date\": \"2024-12-31\"
    }"
done
```

**Expected Files**:
- `data/raw/BTC_USDT_1d.csv` (3 years ~1095 rows)
- `data/raw/ETH_USDT_1d.csv`
- `data/raw/SOL_USDT_1d.csv`

#### Step 2.2: Convert to Qlib Format (30 min)
```bash
# Convert each dataset
for dataset in BTC ETH SOL; do
  curl -X POST "http://localhost:5100/api/data/convert?dataset=crypto_${dataset}_3y&freq=1d"
done
```

**Expected Outcome**: 3 Qlib datasets with 3 years each

---

### Track 3: Alternative Approach - Direct CSV Training (1 hour)
**Goal**: Bypass Qlib data issues, train directly on CSV

#### Step 3.1: Improve Feature Engineering (30 min)
```python
# Add crypto-specific features
def create_advanced_features(df):
    # Current features (24)
    # ... existing features ...
    
    # NEW: Add Alpha158-inspired features
    # Volatility-adjusted returns
    df['vol_adj_return'] = df['returns'] / df['volatility_20']
    
    # Relative strength
    for period in [5, 10, 20]:
        df[f'rsi_{period}'] = calculate_rsi(df['close'], period)
    
    # VWAP deviation
    df['vwap_dev'] = (df['close'] - df['vwap']) / df['vwap']
    
    # Order imbalance proxy
    df['buy_pressure'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    # Trend strength
    df['adx_14'] = calculate_adx(df, 14)
    
    # Total: 24 + 15 = 39 features
    return df
```

**Expected Outcome**: 39 features (more signal)

#### Step 3.2: Hyperparameter Tuning (30 min)
```python
from optuna import create_study

def objective(trial):
    params = {
        'learning_rate': trial.suggest_float('lr', 0.01, 0.1),
        'num_leaves': trial.suggest_int('num_leaves', 31, 255),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'min_data_in_leaf': trial.suggest_int('min_data', 10, 100),
    }
    
    # Train and return validation Sharpe
    model = lgb.train(params, train_data, valid_sets=[valid_data])
    pred = model.predict(X_valid)
    sharpe = calculate_sharpe(y_valid * pred)
    return sharpe

# Run optimization
study = create_study(direction='maximize')
study.optimize(objective, n_trials=50)
best_params = study.best_params
```

**Expected Outcome**: Optimized hyperparameters for our specific crypto data

---

## 📅 Implementation Timeline

### Day 1: Morning (4 hours)
- ✅ **Hour 1**: Track 1 Step 1.1 - Debug Qlib format
- ✅ **Hour 2**: Track 1 Step 1.2 - Official converter
- ✅ **Hour 3**: Track 2 Step 2.1 - Download 3 years data
- ✅ **Hour 4**: Track 1 Step 1.3 + Track 2 Step 2.2 - Validate & convert

**Checkpoint**: Do we have working Qlib data? YES → Continue with Qlib. NO → Track 3

### Day 1: Afternoon (4 hours)
**If Qlib Working**:
- ✅ **Hour 5-6**: Train LightGBM with Alpha158 (3 years data)
- ✅ **Hour 7**: Train LSTM/GRU with same data
- ✅ **Hour 8**: Compare results, select best model

**If Qlib Not Working**:
- ✅ **Hour 5-6**: Track 3 - Advanced feature engineering
- ✅ **Hour 7**: Track 3 - Hyperparameter tuning
- ✅ **Hour 8**: Train and validate

**Success Criteria**: At least ONE model with Sharpe >1.5

### Day 2: Morning (2 hours) - Refinement
- ✅ **Hour 1**: Ensemble best models (if Sharpe >1.5)
- ✅ **Hour 2**: Walk-forward validation

**Target**: Sharpe >2.0, MaxDD <15%

---

## 🎯 Decision Tree

```
START
  │
  ├─ Track 1: Fix Qlib Data
  │   ├─ SUCCESS? → Use Qlib + Alpha158 → Train → GOAL
  │   └─ FAIL? → Continue below
  │
  ├─ Track 2: More Data (3 years)
  │   ├─ SUCCESS? → Retry Qlib OR Direct CSV → GOAL
  │   └─ FAIL? → Continue below
  │
  └─ Track 3: Direct CSV + Tuning
      ├─ Add features (39 total)
      ├─ Hyperparameter optimization
      └─ If Sharpe >1.5 → Ensemble → GOAL
```

---

## 🔍 Specific Solutions for Each Problem

### Problem 1 Solution: Qlib Data Loading

**Root Cause Hypothesis**:
1. Binary file endianness mismatch
2. Incorrect date alignment in calendar
3. Missing metadata in instruments file

**Solution Steps**:
```python
# Step 1: Use Qlib's official DumpDataUpdate
from qlib.data import D
from qlib.contrib.data.handler import DumpDataUpdate

# Read our CSV
df = pd.read_csv('data/raw/BTC_USDT_1d.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
df = df.set_index('datetime')

# Rename columns to match Qlib convention
df = df.rename(columns={
    'open': '$open',
    'close': '$close',
    'high': '$high',
    'low': '$low',
    'volume': '$volume'
})

# Use Qlib's dumper
update = DumpDataUpdate(
    csv_path='data/raw/BTC_USDT_1d.csv',
    qlib_dir='data/qlib/crypto_fixed',
    freq='day',
    max_workers=1,
    date_field_name='datetime',
    symbol_field_name='symbol',  # Add symbol column to CSV
    exclude_fields=['timestamp']
)

update.dump()
```

**Alternative**: Use Qlib's Yahoo Finance downloader as reference
```python
# See: qlib/scripts/data_collector/yahoo/collector.py
# Adapt for crypto using CCXT
```

---

### Problem 2 Solution: More Data

**Quick Win**: Use Binance's free historical data
```python
import ccxt
import pandas as pd

exchange = ccxt.binance()

# Download max available data (usually 1000 candles per request)
all_data = []
since = exchange.parse8601('2022-01-01T00:00:00Z')

while True:
    candles = exchange.fetch_ohlcv('BTC/USDT', '1d', since=since, limit=1000)
    if not candles:
        break
    all_data.extend(candles)
    since = candles[-1][0] + 86400000  # Next day
    
df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df.to_csv('data/raw/BTC_USDT_1d_3years.csv')
```

**Expected**: ~1095 rows (3 years × 365 days)

---

### Problem 3 Solution: Model Performance

**Why Current Model Fails**:
1. ❌ Only 221 training days
2. ❌ Only 24 features (too simple)
3. ❌ Early stopping at iteration 1 (severe overfitting)
4. ❌ Wrong strategy (threshold-based → should be ranking-based)

**Fix**:
```python
# 1. More data (Track 2)
# 2. Better features (39 instead of 24)
# 3. Prevent overfitting
lgb_params = {
    'learning_rate': 0.01,  # Lower LR
    'num_boost_round': 500,  # More rounds
    'early_stopping_rounds': 100,  # More patience
    'min_data_in_leaf': 50,  # Stricter
    'bagging_fraction': 0.7,  # More regularization
}

# 4. Better strategy (Top-K ranking like research papers)
from qlib.contrib.strategy import TopkDropoutStrategy

# Long top 20%, short bottom 20%, hold middle 60%
```

**Expected Improvement**: Sharpe from -0.25 → +1.5 to +2.5

---

## ✅ Success Metrics

### Minimum Viable Goal
- ✅ Sharpe Ratio: >1.5 (good)
- ✅ Max Drawdown: <20%
- ✅ Beats buy-and-hold by 50%

### Target Goal  
- 🎯 Sharpe Ratio: >2.0 (excellent)
- 🎯 Max Drawdown: <15%
- 🎯 Consistent across train/valid/test

### Stretch Goal
- 🚀 Sharpe Ratio: >3.0 (research-level)
- 🚀 Max Drawdown: <10%
- 🚀 Ensemble of 3 models

---

## 🚀 Quick Start Commands

```bash
# Start here
cd /Users/chadwyatt/Code/trading/qlib-2

# Track 1: Fix Qlib (try this first)
python scripts/fix_qlib_data.py

# Track 2: Download more data
python scripts/download_3years_data.py

# Track 3: Direct CSV training  
python scripts/train_simple_crypto_model.py --advanced-features --tune-hyperparams

# Validate
python tests/validate_model_performance.py --target-sharpe 2.0
```

---

## 📊 Expected Outcomes

| Track | Time | Success Probability | Sharpe Expectation |
|-------|------|--------------------|--------------------|
| Track 1 (Qlib Fix) | 2-3 hours | 70% | 2.5-3.2 |
| Track 2 (More Data) | 1-2 hours | 90% | 1.5-2.5 |
| Track 3 (Direct CSV) | 1 hour | 80% | 1.2-2.0 |
| **Combined** | **4-6 hours** | **95%** | **2.0-3.2** |

---

## 🎯 Final Deliverable

When successful, we'll have:

1. ✅ **Working Qlib dataset** (Track 1) OR **3 years CSV data** (Track 2)
2. ✅ **Trained model** with Sharpe >2.0
3. ✅ **Backtest results** showing MaxDD <15%
4. ✅ **Production config** saved to `models/best_crypto_model.json`
5. ✅ **Deployment script** `scripts/deploy_best_model.py`

**Output**:
```json
{
  "model": "LightGBM_Crypto_3Y",
  "sharpe_ratio": 2.47,
  "max_drawdown": -11.2,
  "total_return": 47.3,
  "win_rate": 0.63,
  "status": "GOAL_ACHIEVED",
  "ready_for_production": true
}
```

---

## 🔄 Next Steps After Plan

1. Choose starting track (recommend: Track 2 first for quick data)
2. Execute in parallel where possible
3. Checkpoint at 4 hours
4. Pivot to best-performing track
5. Achieve goal within 6 hours

**Let's begin!** 🚀
