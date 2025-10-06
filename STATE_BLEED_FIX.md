# Qlib State Bleed Fix

## Problem Description

The MCP server was experiencing state bleed across tool calls due to qlib's global state persistence. Since the MCP server runs as a single long-lived Python process, qlib's internal state (`qlib.config.C` and `qlib.data.cache.H`) was being shared across multiple tool invocations.

### Root Causes

1. **Invalid `_inited` flag**: The code checked `qlib.__dict__.get('_inited', False)` but qlib doesn't actually use this attribute internally
2. **Global config persistence**: `qlib.config.C` retains `provider_uri` and other settings between calls
3. **Cache persistence**: `qlib.data.cache.H` (memory cache for calendar, instruments, features) persists across calls
4. **Workflow state**: `qlib.workflow.R` (recorder) state can leak between experiments

### Symptoms

- Models trained with wrong dataset (e.g., training on `crypto_btc_daily` when requesting `crypto_btc_full`)
- Zero training samples despite valid data
- Models collapsing to single tree
- Config showing previous dataset path in logs

## Solution

### Key Insight

After investigation, the solution is simpler than initially thought: **qlib.init() already handles re-initialization correctly**. The real problem is the **memory cache (H)** which persists data between init calls. By clearing the cache before each init, we prevent data bleed while letting qlib manage its own config state.

### Implementation

Created `src/utils/qlib_state.py` with two key functions:

#### 1. `clear_qlib_cache()`
Clears qlib's memory cache (H):
- **Cache (H)**: Clears memory cache for calendar, instruments, and features
- **Simple & Safe**: Doesn't touch qlib's internal config structure
- **Fast**: Only clears data, not entire state

```python
from utils.qlib_state import clear_qlib_cache

clear_qlib_cache()  # Call before re-initializing qlib
```

#### 2. `init_qlib_clean(provider_uri, region, **kwargs)`
Initializes qlib with a clean cache:
- Automatically calls `clear_qlib_cache()` first
- Disables expression/dataset caching by default
- Lets qlib handle its own re-initialization
- Ensures each tool call starts with fresh data

```python
from utils.qlib_state import init_qlib_clean

success = init_qlib_clean(
    provider_uri="/path/to/data",
    region="cn"
)
```

#### 3. `get_qlib_config_info()`
Returns current qlib configuration for debugging:
- `provider_uri`: Current data provider path
- `region`: Current market region  
- `cache_enabled`: Cache configuration status

```python
from utils.qlib_state import get_qlib_config_info

config = get_qlib_config_info()
logger.info(f"Current qlib state: {config}")
```

**Note**: This function safely handles cases where qlib config attributes may not be accessible.

### Files Modified

1. **`src/utils/qlib_state.py`** (NEW)
   - State management utilities

2. **`src/models/trainer.py`**
   - Replaced manual `_inited` flag manipulation with `init_qlib_clean()`
   - Added config logging for debugging

3. **`src/backtesting/engine.py`**
   - Replaced conditional initialization with `init_qlib_clean()`
   - Ensures clean state for each backtest

4. **`src/serving/predictor.py`**
   - Replaced conditional initialization with `init_qlib_clean()`
   - Ensures clean state for predictions

### Testing

Created `tests/test_state_bleed_fix.py` with tests for:
- ✅ Cache clearing functionality
- ✅ Clean re-initialization with different paths
- ✅ Multiple sequential initializations
- ✅ Cache isolation between inits

Run tests:
```bash
python tests/test_state_bleed_fix.py
```

**Results**: All tests pass ✅

## Best Practices

### For MCP Tool Developers

1. **Always use `init_qlib_clean()`** instead of direct `qlib.init()`
2. **Log config state** before/after initialization for debugging
3. **Disable caching** in MCP contexts (already default in `init_qlib_clean()`)
4. **Never rely on global state** between tool calls

### Example Usage

```python
from utils.qlib_state import init_qlib_clean, get_qlib_config_info
import logging

logger = logging.getLogger(__name__)

async def my_mcp_tool(dataset_ref: str):
    """MCP tool that uses qlib"""
    # Log current state
    logger.info(f"Before init: {get_qlib_config_info()}")
    
    # Initialize cleanly
    dataset_path = f"/data/qlib/{dataset_ref}"
    success = init_qlib_clean(
        provider_uri={"day": dataset_path},
        region="cn"
    )
    
    if not success:
        raise RuntimeError(f"Failed to init qlib for {dataset_ref}")
    
    # Log new state
    logger.info(f"After init: {get_qlib_config_info()}")
    
    # ... rest of tool logic ...
```

## Alternative Approaches Considered

### 1. Process Isolation (Not Implemented)
Spawn a fresh Python process for each tool call.

**Pros:**
- Complete isolation guaranteed
- No state can leak

**Cons:**
- Significant overhead (process startup, import time)
- Complexity in IPC
- Slower for rapid successive calls

**Decision:** Not needed - proper state clearing is sufficient and much faster

### 2. Subprocess per Tool (Not Implemented)
Use `subprocess` or `multiprocessing` for each qlib operation.

**Pros:**
- Strong isolation
- Can kill runaway processes

**Cons:**
- High overhead
- Serialization complexity for large models/data
- Harder to debug

**Decision:** Not needed - state management approach is cleaner

### 3. Manual State Tracking (Abandoned)
Continue using `_inited` flag but track state manually.

**Pros:**
- Minimal code changes

**Cons:**
- **Doesn't work** - qlib doesn't use `_inited`
- Still leaves cache and config bleed
- Fragile and error-prone

**Decision:** This was the original approach that failed

## Verification

To verify the fix works:

1. **Check logs** - Should see different `provider_uri` in logs for different datasets
2. **Run tests** - `python tests/test_state_bleed_fix.py`
3. **Test multiple tool calls**:
   ```python
   # In MCP client
   await train_model(dataset_ref="crypto_btc_daily", ...)
   await train_model(dataset_ref="crypto_btc_full", ...)  # Should use correct dataset
   ```
4. **Verify training data** - Logs should show correct number of samples for each dataset

## References

- [Qlib Documentation - Initialization](https://qlib.readthedocs.io/en/latest/start/initialization.html)
- [Qlib Documentation - Data Cache](https://qlib.readthedocs.io/en/latest/component/data.html)
- [Qlib FAQ - Cache Clearing](https://qlib.readthedocs.io/en/stable/FAQ/FAQ.html)
- [Qlib GitHub Issue #159 - Cache Reset](https://github.com/microsoft/qlib/issues/159)

## Future Improvements

1. **Monitor state metrics** - Add logging to track state resets in production
2. **Benchmark overhead** - Measure performance impact of state clearing
3. **Consider process pools** - If overhead becomes significant, could use process pool with max reuse count
4. **Upstream contribution** - Consider proposing `qlib.reset()` method to qlib project
