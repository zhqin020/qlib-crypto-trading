# MCP Server Setup - Qlib Crypto Trading

## ✅ Working Configuration

The MCP server is **now working** and ready to connect to Claude!

### Add to Claude Code MCP Settings

Add this to your Claude Code MCP configuration file (usually `~/.config/claude/mcp.json` or similar):

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2"
    }
  }
}
```

**Note**: Changed from `src.mcp_server.server` to `src.mcp_server` (no `.server` suffix).

---

## Available Tools (15 total)

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

## Verification

The MCP server has been tested and verified to:
- ✅ Respond to `initialize` request
- ✅ List all 15 tools correctly
- ✅ Use proper JSON-RPC 2.0 protocol
- ✅ Handle async operations correctly

### Manual Test

You can test the server manually:

```bash
cd /Users/chadwyatt/Code/trading/qlib-2
python -m src.mcp_server
```

Then send (on stdin):
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
```

You should get:
```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{...},"serverInfo":{"name":"qlib-crypto-trading","version":"1.16.0"}}}
```

---

## What Was Fixed

### Original Issue
- MCP config caused "infinite loading" in Claude
- Server wasn't responding to initialization

### Root Cause
1. Wrong module path: `src.mcp_server.server` → caused import warning
2. Missing `__main__.py` with proper async MCP pattern
3. Incorrect server startup code

### Solution Applied
1. ✅ Created `/src/mcp_server/__main__.py` with proper async pattern
2. ✅ Used correct MCP SDK pattern:
   ```python
   async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
       init_options = app.create_initialization_options()
       await app.run(read_stream, write_stream, init_options)
   ```
3. ✅ Changed config to use `src.mcp_server` (not `src.mcp_server.server`)

---

## Production Notes

### Code Paths
The MCP server uses the **same production code** as the UI/API:
- ✅ Official Qlib converter (`official_qlib_converter.py`)
- ✅ Fail-fast error handling (no fallbacks)
- ✅ Real-time process monitoring
- ✅ No hardcoded test data

### Safety
- All MCP tool calls go through the same validation as API calls
- Errors fail immediately with clear messages
- No silent fallbacks that could hide issues

---

## Usage Examples

Once connected to Claude, you can use natural language:

**Example 1: Download Data**
```
"Use the qlib-trading MCP to get historical BTC/USDT data from 2024-01-01 to 2024-12-31"
```

**Example 2: Train Model**
```
"Train a LightGBM model on the crypto_btc_full dataset using Alpha158 features via qlib-trading MCP"
```

**Example 3: Run Backtest**
```
"Run a backtest on model lightgbm_20251006_104532 using the qlib-trading MCP server"
```

---

## Troubleshooting

### If Claude shows "infinite loading"

1. **Check the config path is correct**:
   ```json
   "cwd": "/Users/chadwyatt/Code/trading/qlib-2"
   ```

2. **Verify Python can run the module**:
   ```bash
   cd /Users/chadwyatt/Code/trading/qlib-2
   python -m src.mcp_server --help
   ```

3. **Check Python version** (needs 3.8+):
   ```bash
   python --version
   ```

4. **Verify MCP dependencies installed**:
   ```bash
   pip install mcp
   ```

### If tools don't appear

1. Restart Claude Code
2. Check MCP server logs in Claude Code settings
3. Verify the server responds to initialization (see Manual Test above)

---

## Summary

- ✅ MCP server is **working and tested**
- ✅ 15 tools available for crypto trading
- ✅ Uses production code (no fallbacks, no test data)
- ✅ Ready to connect to Claude Code

**Just add the config to Claude and restart!**

---

## Troubleshooting: State Bleed Issues

### Symptoms:
- Model trained with wrong dataset
- Zero training samples despite valid data
- Config showing previous dataset path
- Unexpected calendar dates (stock market hours vs 24/7 crypto)

### Solution:
All MCP tools automatically use `init_qlib_clean()` which:
- **Clears qlib memory cache** - Prevents data contamination from previous runs
- **Registers 24/7 crypto calendar** - Ensures continuous trading hours
- **Validates initialization** - Returns False if cache clear fails
- **Protects against concurrent races** - Async lock prevents simultaneous inits

### Implementation Details:
See `src/utils/qlib_state.py` for the complete implementation:

```python
# Synchronous usage (scripts)
from utils.qlib_state import init_qlib_clean
success = init_qlib_clean(provider_uri="data/qlib/crypto", region="cn")

# Async usage (MCP tools)
from utils.qlib_state import init_qlib_clean_async
success = await init_qlib_clean_async(provider_uri="data/qlib/crypto", region="cn")
```

### What Gets Cleared:
1. **Qlib cache (H)**: Calendar, instruments, features data
2. **Previous calendar provider**: Replaced with 24/7 crypto calendar
3. **Provider URI**: Set to requested dataset path
4. **Expression/dataset caches**: Disabled by default

### Verification:
Check logs for these messages:
```
INFO: Clearing qlib cache (H)...
INFO: Successfully cleared qlib cache
INFO: Crypto calendar registered
INFO: Initializing qlib with provider_uri: /path/to/data
INFO: Qlib initialized successfully
```

### If State Bleed Still Occurs:
1. Check that tools are using `init_qlib_clean()` (not direct `qlib.init()`)
2. Verify cache clear succeeded (check return value)
3. Look for error messages during calendar registration
4. Ensure dataset path is correct and accessible

See [STATE_BLEED_FIX.md](STATE_BLEED_FIX.md) for full technical details.
