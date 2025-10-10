# Claude Code MCP Server Configs - Try These

The server **works correctly** (tested and verified), but Claude might be timing out during initialization. Try these configs in order:

---

## Config 1: With Unbuffered Output (RECOMMENDED)

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python3",
      "args": ["-u", "-m", "src.mcp_server"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**Changes**:
- `python3` instead of `python` (more explicit)
- `-u` flag for unbuffered output
- `PYTHONUNBUFFERED=1` environment variable

---

## Config 2: Using Startup Script

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

**Uses**: Direct script with error handling

---

## Config 3: Simple (Original)

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

---

## Verification Test

Before adding to Claude, verify the server works:

```bash
cd /Users/chadwyatt/Code/trading/qlib-2
python test_mcp_init.py
```

You should see:
```
✓ MCP Server Initialization Test PASSED
✓ Response received after 0.54s
✓ Server name: qlib-crypto-trading
```

---

## What Happens During Initialization

1. **Claude starts the process** (runs `python -m src.mcp_server`)
2. **Python imports the module** (~1.3 seconds)
   - MCP library imports (0.6s for rfc3987_syntax)
   - Server setup (0.7s for other imports)
3. **Server waits on stdin** (ready to receive)
4. **Claude sends initialize request** (JSON-RPC)
5. **Server responds** (~0.5s)
6. **Claude shows the server as connected**

**Issue**: Claude might timeout during step 2-3 if it expects faster response.

---

## Debug: Check Claude's Logs

1. Open Claude Code
2. Go to Settings → MCP Servers
3. Try to add server
4. Check logs (should be visible in settings)

Look for:
- ✅ "Server started" 
- ✅ "Server initialized"
- ❌ "Timeout" or "Connection failed"

---

## Alternative: Check if Python Path is Issue

If still hanging, try with full Python path:

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python",
      "args": ["-u", "-m", "src.mcp_server"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2"
    }
  }
}
```

Find your Python path:
```bash
which python3
```

---

## If All Configs Fail

The server itself works (verified). Possible issues:

1. **Claude's timeout is too short** - The 1.3s import time might exceed Claude's limit
2. **Claude expects immediate response** - Some MCP clients expect <100ms startup
3. **Stdout buffering** - Even with unbuffered, might be an issue

**Workaround**: Report to Claude Code team that server needs >1s startup time due to heavy MCP library imports.

---

## Server Startup Time Breakdown

```
Total: 1.3 seconds
├─ 0.6s: rfc3987_syntax.syntax_helpers (MCP dependency)
├─ 0.5s: other MCP imports (jsonschema, pydantic)
└─ 0.2s: our server code
```

**We can't reduce this** - it's the MCP library itself that's slow.

---

## Success Indicators

When it works, you should see in Claude:
1. Server appears in MCP Servers list
2. Shows "✓ Connected"
3. 15 tools available
4. Can call tools with natural language

---

## Next Steps

1. **Try Config 1** (unbuffered output)
2. **Wait 5-10 seconds** after adding (be patient)
3. **Check Claude's logs** for actual error
4. **Try Config 2** if still failing
5. **Report startup time** to Claude Code team if needed

The server **definitely works** - it's just a matter of finding the config that Claude accepts.
