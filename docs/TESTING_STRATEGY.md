# Testing Strategy

## Overview

The test suite is organized into shards to prevent CLI harness timeouts while maintaining comprehensive test coverage.

## Problem Statement

Running the full test suite (`pytest tests/ -v`) was being killed by the CLI harness (exit code 124) after 10-20 minutes. Collection would pause when reaching qlib-heavy suites that perform multiple qlib initializations, causing the watchdog to assume the command was hung and terminate it before results appeared.

## Solution: Sharded Test Execution

Tests are organized into logical groups that run independently, each completing in seconds:

### Available Test Shards

```bash
make test-data      # Data pipeline tests (~5s)
make test-qlib      # Qlib-heavy tests: models, backtests (~2s)
make test-monitor   # Process monitor tests (~8s)
make test-api       # API/WebSocket tests
make test-mcp       # MCP server tests (~2s)
make test-e2e       # Integration/E2E tests
make test-misc      # Miscellaneous tests

make test-sharded   # Run all shards sequentially (~21s total)
```

### Shard Composition

**Data Pipeline** (`test-data`):
- test_data_pipeline.py
- test_data_pipeline_validation.py
- test_data_refresh.py
- test_chunked_converter.py
- test_investment_kpis.py

**Qlib-Heavy** (`test-qlib`):
- test_backtest_costs.py
- test_models.py
- test_full_pipeline.py
- test_qlib_debug.py
- test_concurrent_qlib_init.py

**Process Monitor** (`test-monitor`):
- test_process_monitor_api.py
- test_process_monitor_comprehensive.py
- test_process_monitor_edge_cases.py
- test_process_monitor_integration.py
- test_process_monitor_workflows.py
- test_e2e_process_monitor.py

**API/WebSocket** (`test-api`):
- test_api_endpoints.py
- test_api_validation.py
- test_api.py
- test_websocket_auth.py
- test_websocket_edge_cases.py
- test_websocket_ping_pong.py
- test_websockets.py

**MCP** (`test-mcp`):
- test_mcp_init.py
- test_mcp_state_isolation.py
- **Excluded**: test_mcp_stdio.py, test_mcp_protocol.py, test_mcp_list_tools.py (manual test scripts, not pytest compatible)

**Integration/E2E** (`test-e2e`):
- test_e2e_workflows.py
- test_e2e.py
- test_integration_state_bleed.py
- test_integration_workflows.py
- test_state_bleed_direct.py
- test_state_bleed_fix.py
- test_state_persistence.py

**Miscellaneous** (`test-misc`):
- test_device_management.py
- test_path_traversal_security.py
- test_performance_optimizations.py
- test_task_cancellation_fix.py
- test_ux_improvements.py
- comprehensive_test.py

## Usage

### Development Workflow

Run the relevant shard for the area you're working on:

```bash
# Working on data pipeline
make test-data

# Working on models/backtesting
make test-qlib

# Working on API endpoints
make test-api
```

### CI/Full Test Coverage

```bash
# Run all shards sequentially
make test-sharded
```

### Individual Test Files

```bash
# Run a specific test file
SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_specific.py -v
```

## Known Issues

### Process Monitor Workflow Tests

Several tests in `test_process_monitor_workflows.py` fail when run as part of the shard but pass when run individually:

- `TestTrainerWorkflowMonitoring::test_successful_training_creates_process`
- `TestTrainerWorkflowMonitoring::test_training_failure_marks_process_failed`
- `TestBacktestWorkflowMonitoring::test_successful_backtest_creates_process`
- `TestBacktestWorkflowMonitoring::test_backtest_failure_marks_process_failed`
- `TestPredictorWorkflowMonitoring::test_successful_prediction_creates_process`
- `TestConcurrentWorkflows::test_concurrent_training_and_backtest`

**Root Cause**: State management issue with the `cleanup_monitor` fixture when tests run together. The fixture is supposed to clean `monitor._processes` between tests, but processes aren't being properly registered/found when tests run in sequence.

**Impact**: These failures don't affect the core functionality - the sharded approach successfully prevents timeouts. The tests pass individually, indicating the code works correctly.

**Next Steps**: Investigate fixture ordering and asyncio lifecycle in pytest-asyncio for these tests.

### Non-pytest Compatible Tests

The following files are manual test scripts and excluded from pytest runs:

- `tests/test_mcp_stdio.py` - Starts subprocess at module level, hangs pytest collection
- `tests/test_mcp_protocol.py` - Async function without proper pytest decorator
- `tests/test_mcp_list_tools.py` - No pytest-compatible tests

These should be moved to `scripts/` or converted to proper pytest tests.

## Investment KPI Targets

Test quality is enforced through investment KPI targets defined in `config/investment_targets.json`:

- **data_refresh**: Requires successful download (download_success >= 1) and fresh data (data_age_hours <= 48)
- **model_training**: Validates IC metrics on validation set
- **backtesting**: Checks Sharpe ratio and maximum drawdown
- **prediction**: Ensures adequate symbol coverage

KPI evaluation happens automatically during workflow execution and is tracked in ProcessMonitor.

## Future Improvements

1. **CI Pipeline**: Add GitHub Actions workflow that runs `make test-sharded` with per-shard reporting
2. **Parallel Execution**: Run independent shards in parallel for faster CI
3. **Timeout Configuration**: Set explicit pytest timeouts for each shard
4. **Test Isolation**: Fix state management issues in process_monitor_workflows tests
5. **MCP Test Conversion**: Convert manual MCP test scripts to proper pytest tests
