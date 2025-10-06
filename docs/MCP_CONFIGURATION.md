# MCP Server Configuration Guide

## Overview

The Qlib Crypto Trading Platform provides an MCP (Model Context Protocol) server that exposes 15 tools for data management, model training, backtesting, and serving. This guide provides the authoritative configuration for connecting Claude Code to the MCP server.

---

## Quick Start (Recommended Configuration)

### Method 1: Shell Wrapper with Logging (RECOMMENDED FOR DEBUGGING)

Best for initial setup and troubleshooting. Provides detailed logs of server startup.

**Configuration:**
```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "/Users/chadwyatt/Code/trading/qlib-2/scripts/start_mcp_server.sh",
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2"
    }
  }
}
```

**Pros:**
- Clean PYTHONPATH handling
- Simple configuration
- Startup messages logged to stderr
- Production-ready

**Cons:**
- Requires execute permissions on shell script

**Verify permissions:**
```bash
chmod +x /Users/chadwyatt/Code/trading/qlib-2/scripts/start_mcp_server.sh
```

---

### Method 2: Direct Python Module (RECOMMENDED FOR PRODUCTION)

Best for production use after confirming everything works.

**Configuration:**
```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python3",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONPATH": "/Users/chadwyatt/Code/trading/qlib-2/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**Pros:**
- No shell script dependency
- Explicit Python path
- Unbuffered output for immediate responses
- Platform-independent

**Cons:**
- Requires manual PYTHONPATH setup
- No built-in logging

---

### Method 3: Virtual Environment Python (MOST RELIABLE)

Best when system Python path is unclear or using a virtual environment.

**Configuration:**
```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "/Users/chadwyatt/Code/trading/qlib-2/venv/bin/python3",
      "args": ["-u", "-m", "src.mcp_server"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**Pros:**
- Uses exact Python interpreter with all dependencies
- Guaranteed to work if virtual environment is set up
- No PATH issues

**Cons:**
- Hardcoded path to venv
- Must update if venv location changes

**Find your venv path:**
```bash
which python3  # if inside activated venv
# or
ls /Users/chadwyatt/Code/trading/qlib-2/venv/bin/python3
```

---

## Alternative Methods (For Specific Use Cases)

### Method 4: Debug Mode with External Logging

Use this when you need detailed logs in a separate file for troubleshooting.

**Configuration:**
```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "/Users/chadwyatt/Code/trading/qlib-2/mcp_server_debug.sh",
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**Watch logs:**
```bash
tail -f /tmp/mcp_server.log
```

**Pros:**
- Persistent logs in `/tmp/mcp_server.log`
- Detailed startup information
- Easy to share logs for debugging

**Cons:**
- Requires separate shell script
- Logs accumulate over time

**When to use:**
- Initial setup troubleshooting
- Debugging connection issues
- Reporting issues to maintainers

---

### Method 5: Direct Python Script Starter

Use this for development when you want fast iteration.

**Configuration:**
```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python3",
      "args": ["/Users/chadwyatt/Code/trading/qlib-2/mcp_server_start.py"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2"
    }
  }
}
```

**Pros:**
- Minimal startup time
- Self-contained script
- Easy to modify for testing

**Cons:**
- Additional file to maintain
- Not necessary for most users

---

### Method 6: Shell Command with Stderr Redirect

Use this for advanced debugging when you need to capture all stderr output.

**Configuration:**
```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "sh",
      "args": ["-c", "exec python3 -u -m src.mcp_server 2>/tmp/mcp_stderr.log"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/Users/chadwyatt/Code/trading/qlib-2/src"
      }
    }
  }
}
```

**Pros:**
- Captures all stderr including errors
- No separate script needed

**Cons:**
- More complex configuration
- Platform-specific (Unix/Linux/macOS only)

---

## Available Tools (15 Total)

Once connected, Claude Code will have access to these tools via natural language:

### Data Management
1. **data_create_snapshot** - Build PIT snapshot for dataset/universe
2. **features_create_set** - Create feature set (Alpha158/360/custom)

### Market Data
3. **market_data_get_quote** - Get real-time quote for crypto symbol
4. **market_data_get_quotes_batch** - Get quotes for multiple symbols
5. **market_data_get_historical** - Get historical OHLCV data
6. **market_data_subscribe** - Subscribe to real-time updates

### Model Training & Experiments
7. **models_train** - Train model against dataset + features
8. **experiments_run_recipe** - Execute experiment recipe (Beginner/Expert)
9. **experiments_tag** - Tag runs (candidate/promoted/archived)

### Backtesting & Serving
10. **backtests_run** - Run backtest using trained model
11. **serving_predict_today** - Generate predictions for current session

### Orchestration
12. **runs_cancel** - Cancel long-running job
13. **notifications_dispatch** - Send notifications (Teams/email)
14. **schedules_create** - Create scheduled job via RRULE

### Knowledge
15. **knowledge_describe_screen** - Retrieve UI screen descriptions

---

## Troubleshooting

### Issue: Claude Shows "Infinite Loading"

**Symptoms:** MCP server appears to be connecting but never finishes initialization.

**Diagnosis Steps:**

1. **Verify server can start independently:**
   ```bash
   cd /Users/chadwyatt/Code/trading/qlib-2
   python3 -m src.mcp_server
   ```
   Press Ctrl+C after 2 seconds if you see no errors.

2. **Check Python version (requires 3.8+):**
   ```bash
   python3 --version
   ```

3. **Verify MCP dependencies installed:**
   ```bash
   pip3 show mcp
   ```

4. **Test initialization manually:**
   ```bash
   cd /Users/chadwyatt/Code/trading/qlib-2
   python3 test_mcp_init.py
   ```
   Should complete in ~0.5-2 seconds.

**Solutions:**
- Use Method 1 (shell wrapper) for automatic PYTHONPATH handling
- Use Method 3 (venv path) if Python environment is unclear
- Check Claude Code logs in Settings → MCP Servers
- Verify `cwd` path is correct and absolute

---

### Issue: Tools Don't Appear in Claude

**Symptoms:** Server connects but no tools are available.

**Solutions:**
1. Restart Claude Code completely
2. Remove and re-add the MCP server configuration
3. Check server logs for errors during initialization
4. Verify the server responds to list_tools:
   ```bash
   python3 test_mcp_list_tools.py
   ```

---

### Issue: Import Errors or Module Not Found

**Symptoms:** Errors like "ModuleNotFoundError: No module named 'src.mcp_server'"

**Solutions:**
1. **Check PYTHONPATH is set correctly:**
   - Method 1 handles this automatically
   - Method 2 requires explicit PYTHONPATH in env
   - Method 3 doesn't need PYTHONPATH if using venv

2. **Verify module structure:**
   ```bash
   ls -la /Users/chadwyatt/Code/trading/qlib-2/src/mcp_server/
   ```
   Should show: `__init__.py`, `__main__.py`, `server.py`

3. **Use correct module path:**
   - ✅ Correct: `src.mcp_server`
   - ❌ Wrong: `src.mcp_server.server`

---

### Issue: Server Starts But Crashes

**Symptoms:** Server appears to start then immediately exits.

**Enable debugging:**
1. Use Method 4 (debug mode) to capture logs
2. Watch logs while connecting:
   ```bash
   tail -f /tmp/mcp_server.log
   ```
3. Look for stack traces or error messages

**Common causes:**
- Missing dependencies: `pip3 install -r requirements.txt`
- Permission issues: Check file permissions
- Port conflicts: MCP uses stdio, so unlikely

---

### Issue: Slow Startup Time

**Expected behavior:** Server takes 1-2 seconds to initialize due to MCP library imports.

**Breakdown:**
- 0.6s: MCP library imports (rfc3987_syntax)
- 0.5s: Additional dependencies (jsonschema, pydantic)
- 0.2s: Server code initialization
- **Total: ~1.3-1.7 seconds**

**This is normal and cannot be optimized further.** Claude Code should wait at least 3-5 seconds before timing out.

---

## Advanced Configuration

### Environment Variables

All methods support custom environment variables:

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "...",
      "args": [...],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/Users/chadwyatt/Code/trading/qlib-2/src",
        "LOG_LEVEL": "DEBUG",
        "QLIB_DATA_PATH": "/custom/path/to/data"
      }
    }
  }
}
```

**Available variables:**
- `PYTHONUNBUFFERED`: Set to "1" for immediate output
- `PYTHONPATH`: Add project paths for imports
- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `QLIB_DATA_PATH`: Override default data directory

---

### Logging Configuration

The MCP server logs to stderr by default. Configure logging in the environment:

**Method 1 (Shell Wrapper):**
- Logs automatically go to stderr
- Claude Code captures these in its MCP logs
- No additional configuration needed

**Method 4 (Debug Mode):**
- Logs written to `/tmp/mcp_server.log`
- Includes startup information
- Rotated on each server start

**Method 6 (Stderr Redirect):**
- Logs written to `/tmp/mcp_stderr.log`
- Captures all error output
- Must manually clear old logs

---

## Testing & Verification

### Manual Protocol Test

Test the MCP server responds to JSON-RPC correctly:

```bash
cd /Users/chadwyatt/Code/trading/qlib-2
python3 -m src.mcp_server
```

Send (paste this on stdin):
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
```

Expected response (within 1 second):
```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{...},"serverInfo":{"name":"qlib-crypto-trading","version":"1.16.0"}}}
```

---

### Automated Tests

Run the included test scripts:

```bash
cd /Users/chadwyatt/Code/trading/qlib-2

# Test initialization
python3 test_mcp_init.py

# Test tool listing
python3 test_mcp_list_tools.py

# Test full protocol
python3 test_mcp_protocol.py
```

All tests should complete successfully in under 2 seconds.

---

## Usage Examples

Once connected to Claude Code, interact with the MCP server using natural language:

### Example 1: Download Historical Data
```
"Use the qlib-trading MCP to get historical BTC/USDT data from 2024-01-01 to 2024-12-31"
```

### Example 2: Train a Model
```
"Train a LightGBM model on the crypto_btc_full dataset using Alpha158 features via qlib-trading MCP"
```

### Example 3: Run Backtest
```
"Run a backtest on model lightgbm_20251006_104532 with low costs and weekly rebalancing using the qlib-trading MCP"
```

### Example 4: Get Live Quote
```
"What's the current BTC/USDT price via the qlib-trading MCP server?"
```

### Example 5: Generate Predictions
```
"Generate today's predictions for the trained model using qlib-trading MCP"
```

---

## Production Notes

### Code Quality
The MCP server uses the **same production code** as the UI/API:
- Official Qlib converter (no test data)
- Fail-fast error handling (no silent fallbacks)
- Real-time process monitoring
- Consistent validation across all interfaces

### Safety
- All MCP tool calls go through the same validation as API calls
- Errors fail immediately with clear messages
- No silent fallbacks that could hide issues
- All operations logged for audit trail

### Performance
- Async operations for concurrent tool calls
- Efficient data streaming for large datasets
- Connection pooling for market data providers
- Caching where appropriate

---

## Migration from Older Configs

If you have an older configuration that used:
- `src.mcp_server.server` → Change to `src.mcp_server`
- `python` → Change to `python3` for clarity
- Missing PYTHONPATH → Add via env or use Method 1
- Hardcoded paths → Make paths absolute and generic

See `docs/MCP_CONSOLIDATION_REPORT.md` for detailed migration guide.

---

## Summary

**For most users:**
- Start with **Method 1** (Shell Wrapper) - easiest and most reliable
- Move to **Method 2** (Direct Python) once comfortable
- Use **Method 4** (Debug Mode) if you encounter issues

**Configuration checklist:**
- ✅ Absolute path for `cwd`
- ✅ Correct Python interpreter (python3 or venv path)
- ✅ Execute permissions on shell scripts
- ✅ PYTHONUNBUFFERED=1 for responsive output
- ✅ Wait 3-5 seconds for initialization

**Verification checklist:**
- ✅ Server starts without errors
- ✅ Initialization completes in < 2 seconds
- ✅ 15 tools appear in Claude Code
- ✅ Can execute at least one tool successfully

---

## Support

If you continue to experience issues:

1. **Check the logs** using Method 4 (Debug Mode)
2. **Run manual tests** to verify server works independently
3. **Verify environment** (Python version, dependencies, paths)
4. **Review this guide** for configuration issues
5. **Check Claude Code version** - ensure MCP protocol 2024-11-05 support

The MCP server is tested and verified to work correctly. Most issues are configuration-related and can be resolved by following this guide.
