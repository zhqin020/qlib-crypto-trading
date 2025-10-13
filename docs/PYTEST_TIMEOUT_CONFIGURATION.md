# Pytest Timeout Configuration

**Issue:** #6
**Status:** ✅ Implemented

## Overview

Replaced system `timeout` commands with pytest-timeout plugin for better control, clearer error messages, and cross-platform compatibility.

## Configuration

### Global Defaults (pytest.ini)

```ini
[pytest]
timeout = 300  # 5 minute default
timeout_method = thread  # Cross-platform compatible
timeout_func_only = true  # Only timeout test functions, not fixtures
```

### Per-Shard Recommended Timeouts

Based on observed execution times with 10x safety margin:

| Shard | Observed | Timeout | Command |
|-------|----------|---------|---------|
| data | ~5s | 60s | `pytest --timeout=60 tests/test_data_*.py` |
| qlib | ~2s | 120s | `pytest --timeout=120 tests/test_*_costs.py tests/test_models.py` |
| monitor | ~8s | 120s | `pytest --timeout=120 tests/test_process_monitor_*.py` |
| api | ~2s | 60s | `pytest --timeout=60 tests/test_api*.py tests/test_websocket*.py` |
| mcp | ~2s | 30s | `pytest --timeout=30 tests/test_mcp*.py` |
| e2e | ~1s | 180s | `pytest --timeout=180 tests/test_e2e*.py tests/test_integration*.py` |
| misc | ~1s | 60s | `pytest --timeout=60 tests/test_device*.py tests/test_ux*.py` |

## Usage

### Default Behavior

```bash
# Uses 300s timeout from pytest.ini
pytest tests/test_api.py
```

### Override Timeout

```bash
# Stricter timeout for fast tests
pytest --timeout=30 tests/test_unit.py

# Disable timeout for debugging
pytest --timeout=0 tests/test_debug.py
```

### Per-Test Decorators

```python
import pytest

@pytest.mark.timeout(30)
def test_fast_operation():
    """Should complete in <30s"""
    pass

@pytest.mark.timeout(300)
def test_qlib_training():
    """Qlib training can be slow"""
    pass

@pytest.mark.timeout(0)  # Disable
def test_with_debugger():
    """For interactive debugging"""
    import pdb; pdb.set_trace()
    pass
```

## Benefits Over System Timeout

### ❌ Before (system timeout)

```bash
timeout 30 pytest tests/test_api.py
```

**Problems:**
- Platform-dependent (GNU vs BSD timeout)
- No per-test granularity
- Unclear error messages ("Command timed out")
- Kill signal may not clean up properly
- No pytest integration

### ✅ After (pytest-timeout)

```bash
pytest --timeout=30 tests/test_api.py
```

**Advantages:**
- ✅ Cross-platform (Linux, macOS, Windows)
- ✅ Per-test granularity via decorators
- ✅ Clear error messages with stack traces
- ✅ Proper cleanup via pytest lifecycle
- ✅ Can disable for debugging (`--timeout=0`)
- ✅ Thread dumps on timeout
- ✅ Native pytest reporting

## Timeout Methods

### Thread Method (Default)

```ini
timeout_method = thread
```

**Pros:**
- Works with debuggers (pdb, ipdb)
- Cross-platform
- More predictable cleanup

**Cons:**
- Slightly slower timeout detection (~1s)

### Signal Method

```ini
timeout_method = signal
```

**Pros:**
- Faster timeout detection
- Lower overhead

**Cons:**
- Unix-only
- Doesn't work with debuggers
- Can interfere with signal handling

**Recommendation:** Use `thread` method (default)

## Error Messages

### Timeout Error Example

```
TIMEOUT: tests/test_models.py::test_training - 120.0s
Location: src/models/trainer.py:450 in do_training
Thread dump:
  File "src/models/trainer.py", line 450, in do_training
    model.fit(dataset)
  File "venv/lib/python3.13/site-packages/qlib/...", line 123
    [stack trace]
```

Much clearer than system timeout: `Command timed out after 2m 0s` ❌

## CI Integration

### Local Development

```bash
# Generous timeout for debugging
pytest --timeout=600 tests/

# Or disable entirely
pytest --timeout=0 tests/
```

### CI

```bash
# Strict timeout for fast feedback
pytest --timeout=60 tests/

# Or per-shard
make test-data   # Uses 60s
make test-qlib   # Uses 120s
```

## Troubleshooting

### Timeout in test_qlib_initialization

**Symptom:** Test times out during qlib initialization

**Causes:**
- Qlib downloading data
- Building cache
- Network issues

**Solutions:**
1. Increase timeout: `@pytest.mark.timeout(600)`
2. Mock initialization in tests
3. Use pre-built qlib data

### Timeout in pytest collection

**Symptom:** `pytest --collect-only` hangs

**Cause:** Module-level code execution (e.g., `test_mcp_stdio.py`)

**Solution:** Add to `pytest.ini`:
```ini
collect_ignore = tests/test_problematic.py
```

### Tests slower in CI

**Symptom:** Tests pass locally but timeout in CI

**Causes:**
- Slower CI runners
- Cold cache
- Resource contention

**Solutions:**
1. Increase CI timeouts by 2-3x
2. Use pytest-timeout's `timeout_func_only = false` in CI
3. Cache dependencies and data

## Migration from System Timeout

### Makefile Updates (Optional)

**Before:**
```makefile
test-data:
    timeout 60 venv/bin/python -m pytest tests/test_data*.py
```

**After:**
```makefile
test-data:
    venv/bin/python -m pytest --timeout=60 tests/test_data*.py
```

**Note:** With pytest.ini configuration, explicit --timeout flags are optional.

## Configuration Reference

### pytest.ini Options

```ini
[pytest]
# Default timeout for all tests (seconds)
timeout = 300

# Timeout method: thread (default) or signal
timeout_method = thread

# Only timeout test functions, not fixtures/setup/teardown
timeout_func_only = true
```

### Command Line Options

```bash
# Override default timeout
pytest --timeout=60

# Disable timeout
pytest --timeout=0

# Change timeout method
pytest --timeout-method=signal
```

### Environment Variables

```bash
# Set timeout via environment
export PYTEST_TIMEOUT=60
pytest tests/

# Disable in CI for debugging
export PYTEST_TIMEOUT=0  # Careful!
```

## References

- pytest-timeout docs: https://github.com/pytest-dev/pytest-timeout
- Issue #6: Add pytest timeout configuration
- pytest.ini: Lines 13-16
- requirements.txt: pytest-timeout>=2.2.0
