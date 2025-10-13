# Parallel Test Execution

## Overview

Issue #4 implements parallel test execution using `pytest-xdist`, enabling faster test runs by utilizing multiple CPU cores simultaneously.

## Quick Start

```bash
# Run all tests in parallel (recommended)
make test-parallel

# Run with maximum speed (loadfile distribution)
make test-parallel-fast

# Traditional sequential execution
make test

# Manual sharded execution (fastest for this codebase)
make test-sharded
```

## Performance Comparison

| Method | Execution Time | CPU Usage | Description |
|--------|---------------|-----------|-------------|
| Sequential | >3 minutes | ~100% | Single-threaded execution |
| **Parallel (loadscope)** | **~30s** | **366%** | **Multi-core with class grouping** |
| Parallel (loadfile) | ~40s | 303% | Multi-core with file grouping |
| Sharded | ~21s | ~100% per shard | Manual test grouping (optimized) |

## How It Works

### pytest-xdist Installation

```bash
pip install "pytest-xdist>=3.5.0"
```

### Worker Allocation

pytest-xdist automatically detects CPU cores and spawns worker processes:
- **Auto detection**: `-n auto` (recommended)
- **Manual**: `-n 4` (4 workers)
- **CPU count**: `-n logical` (all logical cores)

### Test Distribution Strategies

#### 1. LoadScope Distribution (`--dist loadscope`)
**Recommended for this codebase**

Groups tests by class/module to minimize initialization overhead:
```bash
pytest tests/ -n auto --dist loadscope
```

**Advantages:**
- Reduces qlib re-initialization
- Better test isolation
- Consistent with existing test structure

**Results:** ~30s execution, 366% CPU usage

#### 2. LoadFile Distribution (`--dist loadfile`)
Distributes entire test files to workers:
```bash
pytest tests/ -n auto --dist loadfile
```

**Advantages:**
- Maximum parallelization
- Simple distribution logic

**Results:** ~40s execution (slower due to initialization overhead)

## Configuration

### pytest.ini

```ini
[pytest]
# Standard markers
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    requires_server: marks tests requiring API server
    mcp: marks MCP server tests
    data: marks data pipeline tests
    model: marks model training tests
    backtest: marks backtesting tests
    api: marks API tests
    monitor: marks process monitor tests

# pytest-xdist configuration
[pytest:xdist]
looponfail = False
```

### Test Markers

Use markers to group and filter tests:

```python
# Mark tests that require external services
@pytest.mark.requires_server
async def test_api_endpoint():
    ...

# Mark slow tests
@pytest.mark.slow
def test_full_backtest():
    ...
```

Run specific groups:
```bash
# Skip tests requiring server
pytest -m "not requires_server" -n auto

# Run only unit tests
pytest -m unit -n auto

# Run MCP tests in parallel
pytest -m mcp -n auto
```

## Makefile Targets

### test-parallel
**Recommended for CI/CD and local development**

```makefile
test-parallel:
    SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/ -n auto --dist loadscope -v
```

Uses loadscope distribution for optimal balance of speed and isolation.

### test-parallel-fast
**Experimental: maximum parallelization**

```makefile
test-parallel-fast:
    SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/ -n auto --dist loadfile -v
```

Uses loadfile distribution for maximum worker utilization.

## Known Issues

### 1. API Validation Tests
**Status:** Expected failures when server not running

```
FAILED tests/test_api_validation.py::test_train_model_validation
FAILED tests/test_api_validation.py::test_backtest_validation
FAILED tests/test_api_validation.py::test_prediction_validation
FAILED tests/test_api_validation.py::test_process_validation
FAILED tests/test_api_validation.py::test_model_endpoint_validation
```

**Solution:** These tests should be marked with `@pytest.mark.requires_server` and run separately:
```bash
# Run with server
./scripts/start_server.sh &
pytest -m requires_server -n auto
```

### 2. Process Monitor Workflow Test
**Status:** Intermittent failure due to timing/isolation

```
FAILED tests/test_process_monitor_workflows.py::TestPredictorWorkflowMonitoring::test_successful_prediction_creates_process
```

**Workaround:** This test passes when run individually but may fail in parallel due to shared state. Related to Issue #1 (remaining 6 failing tests in full shard).

## Best Practices

### 1. Test Isolation
Ensure tests don't share state:
```python
@pytest.fixture(autouse=True)
async def reset_monitor():
    """Reset monitor state before each test"""
    monitor = ProcessMonitor()
    await monitor.reset()
    yield
    await monitor.reset()
```

### 2. Resource Management
Close resources properly to avoid worker hangs:
```python
async def test_example():
    async with resource() as r:
        # Test code
        pass
    # Resource automatically closed
```

### 3. Marker Usage
Mark tests appropriately for filtering:
```python
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_server
async def test_full_workflow():
    ...
```

## Why Sharded Execution Is Still Faster

The manual sharded approach (`make test-sharded`) runs in ~21s compared to parallel execution's ~30s because:

1. **Optimized grouping**: Tests are manually grouped to minimize qlib initialization
2. **Sequential shards**: Each shard runs independently without inter-process overhead
3. **Tuned for this codebase**: Grouping reflects actual test dependencies and initialization patterns

**When to use each approach:**
- **Sharded** (`make test-sharded`): Fastest, best for CI/CD critical paths
- **Parallel** (`make test-parallel`): Simple, good for local development
- **Sequential** (`make test`): Debugging, detailed output

## Future Optimizations

### 1. Marker-Based Grouping
Group tests by initialization requirements:
```bash
# Heavy qlib tests
pytest -m "qlib_heavy" -n 2

# Light tests
pytest -m "not qlib_heavy" -n auto
```

### 2. Test Execution Order
Optimize test order to run fast tests first:
```bash
pytest --ff --nf -n auto
```

### 3. Coverage with Parallelization
Combine parallel execution with coverage:
```bash
pytest -n auto --cov=src --cov-report=html
```

Note: Coverage data collection adds ~10-15% overhead.

## References

- pytest-xdist documentation: https://pytest-xdist.readthedocs.io/
- Issue #4: Parallel Test Execution
- Issue #1: Process Monitor Test State Management
- docs/TESTING_STRATEGY.md: Overall testing approach
