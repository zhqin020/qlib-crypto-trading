# Qlib State Bleed - Solution Summary

## Problem
MCP server tool calls were sharing qlib global state, causing dataset paths to bleed between calls. Training on wrong data resulted in zero samples and model failures.

## Root Cause
**qlib.data.cache.H** (memory cache) persists calendar, instruments, and features data across qlib.init() calls in the same Python process.

## Solution
Clear the cache before each qlib.init() call.

### Code Changes

**New file**: `src/utils/qlib_state.py`
```python
def clear_qlib_cache():
    """Clear qlib's memory cache to prevent data bleed"""
    from qlib.data.cache import H
    H.clear()

def init_qlib_clean(provider_uri, region="cn", **kwargs):
    """Initialize qlib with clean cache"""
    clear_qlib_cache()
    qlib.init(provider_uri=provider_uri, region=region, 
              expression_cache=None, dataset_cache=None, **kwargs)
```

**Updated files**:
- `src/models/trainer.py` - Use `init_qlib_clean()` instead of manual init
- `src/backtesting/engine.py` - Use `init_qlib_clean()` instead of manual init  
- `src/serving/predictor.py` - Use `init_qlib_clean()` instead of manual init

### Usage

```python
from utils.qlib_state import init_qlib_clean

# Each tool call gets clean state
success = init_qlib_clean(
    provider_uri={"day": str(dataset_dir)},
    region="cn"
)
```

## Testing
All tests pass ✅:
- Cache clearing works
- Re-initialization with different paths works
- Multiple sequential inits work
- No data bleed between calls

```bash
python tests/test_state_bleed_fix.py
```

## Impact
- ✅ Each MCP tool call uses correct dataset
- ✅ No state bleed across tool invocations
- ✅ Training data samples are correct
- ✅ Models train successfully

## Key Learnings
1. **qlib.init() handles re-initialization** - Don't need to clear config
2. **Cache (H) is the culprit** - Must be cleared explicitly
3. **Keep it simple** - Clear only what's necessary
4. **Disable caching in MCP context** - Set `expression_cache=None`, `dataset_cache=None`
