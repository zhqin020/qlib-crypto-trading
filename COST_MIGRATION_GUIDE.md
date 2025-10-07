# Qlib Cost Configuration Migration Guide

## Quick Reference

### WRONG (Current Implementation)
```python
# ❌ Non-existent parameters
cost_config = {
    "trade_cost": 0.001,    # NOT A REAL PARAMETER
    "slippage": 0.0005,     # NOT A REAL PARAMETER
    "funding_rate": 0.0001, # NOT A REAL PARAMETER
}

# ❌ Passing to executor (executor doesn't accept these)
executor_config = {
    "kwargs": {
        **cost_config  # WRONG LOCATION
    }
}
```

### CORRECT (Required Implementation)
```python
# ✅ Real Qlib Exchange parameters
exchange_kwargs = {
    "open_cost": 0.0005,    # ✅ Cost to open position
    "close_cost": 0.0015,   # ✅ Cost to close position
    "min_cost": 0,          # ✅ Minimum cost
    "impact_cost": 0.0001,  # ✅ Market impact (slippage)
}

# ✅ Pass to backtest() function, NOT executor
portfolio_metric_dict, indicator_dict = qlib_backtest(
    strategy=strategy_config,
    executor=executor_config,
    exchange_kwargs=exchange_kwargs,  # ✅ CORRECT LOCATION
)
```

---

## Changes Required in `/Users/chadwyatt/Code/trading/qlib-2/src/backtesting/engine.py`

### Change 1: Update `get_cost_config()` Function

**BEFORE (Lines 266-315):**
```python
def get_cost_config(costs: str, funding: bool = False) -> Dict[str, Any]:
    cost_configs = {
        "low": {
            "trade_exchange": {"class": "Exchange", "kwargs": {
                "freq": "day",
                "min_cost": 0,
                "trade_unit": None,
                "deal_price": "close",
            }},
            "trade_cost": 0.0005,  # ❌ Wrong parameter
            "slippage": 0.0001,    # ❌ Wrong parameter
        },
        # ... more configs
    }
    config = cost_configs.get(costs, cost_configs["medium"])
    if funding:
        config["funding_rate"] = 0.0001  # ❌ Wrong parameter
    return config
```

**AFTER:**
```python
def get_cost_config(costs: str, funding: bool = False) -> Dict[str, Any]:
    """
    Get exchange cost configuration for crypto trading.

    Returns exchange_kwargs dict to be passed to backtest() function.

    Args:
        costs: Cost level ("low", "medium", "high")
        funding: Include warning about funding rates (not implemented)

    Returns:
        Dict with exchange_kwargs for Qlib backtest
    """
    cost_configs = {
        "low": {
            "freq": "day",
            "limit_threshold": None,      # No price limits for crypto
            "deal_price": "close",
            "open_cost": 0.0002,          # ✅ 0.02% (VIP maker)
            "close_cost": 0.0005,         # ✅ 0.05% (low taker)
            "min_cost": 0,                # ✅ No minimum for crypto
            "impact_cost": 0.00005,       # ✅ 0.005% market impact
        },
        "medium": {
            "freq": "day",
            "limit_threshold": None,
            "deal_price": "close",
            "open_cost": 0.0005,          # ✅ 0.05% (Binance maker)
            "close_cost": 0.001,          # ✅ 0.1% (standard taker)
            "min_cost": 0,
            "impact_cost": 0.0001,        # ✅ 0.01% market impact
        },
        "high": {
            "freq": "day",
            "limit_threshold": None,
            "deal_price": "close",
            "open_cost": 0.001,           # ✅ 0.1% (conservative)
            "close_cost": 0.002,          # ✅ 0.2% (high taker)
            "min_cost": 0,
            "impact_cost": 0.0005,        # ✅ 0.05% market impact
        }
    }

    config = cost_configs.get(costs, cost_configs["medium"])

    if funding:
        logger.warning(
            "Funding rate costs are not natively supported by Qlib Exchange. "
            "Consider implementing a custom Exchange subclass for futures funding rates."
        )

    return config
```

### Change 2: Update `run_backtest()` Function

**BEFORE (Lines 134-181):**
```python
# Step 4: Configure backtest
await monitor.update_progress(process_id, 57.1, f"Configuring backtest (costs={costs}, rebalance={rebalance})", 4)

# Get transaction costs
cost_config = get_cost_config(costs, funding)

# Define executor
executor_config = {
    "class": "SimulatorExecutor",
    "module_path": "qlib.backtest.executor",
    "kwargs": {
        "time_per_step": rebalance,
        "generate_portfolio_metrics": True,
        "verbose": False,
        **cost_config  # ❌ WRONG: Executor doesn't accept these
    },
}

# Run backtest
portfolio_metric_dict, indicator_dict = qlib_backtest(
    start_time="2023-01-01",
    end_time="2024-12-31",
    strategy=strategy_config,
    executor=executor_config,
    benchmark="BTC_USDT",
    # ❌ MISSING: exchange_kwargs parameter
)
```

**AFTER:**
```python
# Step 4: Configure backtest
await monitor.update_progress(process_id, 57.1, f"Configuring backtest (costs={costs}, rebalance={rebalance})", 4)

# Get exchange cost configuration (NOT executor config)
exchange_kwargs = get_cost_config(costs, funding)

# Define executor (WITHOUT cost parameters)
executor_config = {
    "class": "SimulatorExecutor",
    "module_path": "qlib.backtest.executor",
    "kwargs": {
        "time_per_step": rebalance,
        "generate_portfolio_metrics": True,
        "verbose": False,
        # ✅ NO cost parameters here
    },
}

# Run backtest with exchange_kwargs
portfolio_metric_dict, indicator_dict = qlib_backtest(
    start_time="2023-01-01",
    end_time="2024-12-31",
    strategy=strategy_config,
    executor=executor_config,
    benchmark="BTC_USDT",
    exchange_kwargs=exchange_kwargs,  # ✅ CORRECT: Pass costs here
)
```

---

## Testing the Changes

### Test 1: Verify Costs Are Applied

```python
# Run same backtest with different cost levels
results_no_cost = run_backtest(model_id="test", costs="low", ...)
results_med_cost = run_backtest(model_id="test", costs="medium", ...)
results_high_cost = run_backtest(model_id="test", costs="high", ...)

# Verify returns decrease with higher costs
assert results_no_cost["metrics"]["annualized_return"] > \
       results_med_cost["metrics"]["annualized_return"] > \
       results_high_cost["metrics"]["annualized_return"]
```

### Test 2: Check Portfolio Metrics

```python
result = run_backtest(model_id="test", costs="medium", ...)

# Should have both cost series
assert "excess_return_with_cost" in result["portfolio_curve"]
assert "excess_return_without_cost" in result["portfolio_curve"]

# With-cost returns should be lower
with_cost = result["portfolio_curve"]["excess_return_with_cost"]
without_cost = result["portfolio_curve"]["excess_return_without_cost"]
assert sum(with_cost) < sum(without_cost)
```

### Test 3: Validate Cost Impact

```python
# Expected cost impact ranges for daily trading
cost_impacts = {
    "low": (0.005, 0.02),      # 0.5-2% annual impact
    "medium": (0.01, 0.05),    # 1-5% annual impact
    "high": (0.03, 0.10),      # 3-10% annual impact
}

for level, (min_impact, max_impact) in cost_impacts.items():
    result = run_backtest(costs=level, ...)
    impact = (result["no_cost_return"] - result["with_cost_return"])
    assert min_impact <= impact <= max_impact, f"{level} cost impact out of range"
```

---

## Validation Checklist

Before deploying changes:

- [ ] Updated `get_cost_config()` to return correct parameters
- [ ] Removed `trade_cost`, `slippage`, `funding_rate` parameters
- [ ] Added `open_cost`, `close_cost`, `min_cost`, `impact_cost` parameters
- [ ] Set `min_cost=0` for crypto (no minimum fees)
- [ ] Set `limit_threshold=None` for crypto (no price limits)
- [ ] Updated `run_backtest()` to use `exchange_kwargs`
- [ ] Removed cost parameters from `executor_config["kwargs"]`
- [ ] Added `exchange_kwargs=exchange_kwargs` to `qlib_backtest()` call
- [ ] Tested with low/medium/high cost levels
- [ ] Verified returns decrease with higher costs
- [ ] Checked portfolio metrics show cost impact
- [ ] Updated documentation and comments

---

## Expected Behavior After Migration

### Before (Broken)
```
Cost Level: medium
Annualized Return: 45.2%
Sharpe Ratio: 2.15

# ⚠️ Too high - costs not being applied!
```

### After (Correct)
```
Cost Level: medium
Annualized Return: 38.7%  # ✅ Lower due to costs
Sharpe Ratio: 1.92        # ✅ Lower due to cost drag

Cost Impact: 6.5%         # ✅ Realistic cost drag
```

---

## Common Mistakes to Avoid

1. **Passing costs to executor instead of backtest()**
   - Executor doesn't accept cost parameters
   - Must use `exchange_kwargs` in backtest() call

2. **Using wrong parameter names**
   - Not `trade_cost`, use `open_cost` and `close_cost`
   - Not `slippage`, use `impact_cost`
   - Not `funding_rate`, needs custom implementation

3. **Expressing fees incorrectly**
   - 0.0005 = 0.05% (correct)
   - 0.05 = 5% (wrong - way too high!)

4. **Using stock market defaults for crypto**
   - Crypto: no price limits (`limit_threshold=None`)
   - Crypto: no minimum fees (`min_cost=0`)
   - Crypto: lower fee rates (0.05-0.1% typical)

5. **Not testing cost impact**
   - Always verify costs reduce returns
   - Check portfolio metrics diverge
   - Validate cost levels are realistic

---

## Quick Implementation Steps

1. **Backup current file:**
   ```bash
   cp src/backtesting/engine.py src/backtesting/engine.py.backup
   ```

2. **Apply changes to `get_cost_config()`**
   - Replace entire function with corrected version
   - Update return structure to flat dict

3. **Apply changes to `run_backtest()`**
   - Rename `cost_config` to `exchange_kwargs`
   - Remove `**cost_config` from executor kwargs
   - Add `exchange_kwargs=exchange_kwargs` to backtest() call

4. **Test changes:**
   ```bash
   python -m pytest tests/test_backtesting.py -v
   ```

5. **Run integration test:**
   ```bash
   # Test with real model
   python scripts/test_backtest_costs.py
   ```

6. **Commit changes:**
   ```bash
   git add src/backtesting/engine.py
   git commit -m "fix: Use correct Qlib exchange_kwargs for transaction costs"
   ```

---

## Support and References

- **Full Research Report:** `/Users/chadwyatt/Code/trading/qlib-2/QLIB_COST_CONFIGURATION_RESEARCH.md`
- **Qlib Documentation:** https://qlib.readthedocs.io/en/latest/component/backtest.html
- **Qlib Exchange Source:** https://github.com/microsoft/qlib/blob/main/qlib/backtest/exchange.py
- **Example Workflow:** https://github.com/microsoft/qlib/blob/main/examples/workflow_by_code.py

**Questions?** Check the full research report for detailed explanations and examples.
