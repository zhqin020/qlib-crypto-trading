# Fixed MCP Configuration

Claude Code requires the `args` field. Use this configuration:

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "bash",
      "args": ["/Users/chadwyatt/Code/trading/qlib-2/mcp_server_debug.sh"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Or use Python directly:

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python",
      "args": ["-u", "-m", "src.mcp_server"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

## To See Backend Logs

**Option 1 - Using the debug script:**
```bash
tail -f /tmp/mcp_server.log
```

**Option 2 - Using Python directly:**
Since stderr won't be captured with the Python config, you can check if the server is running:
```bash
ps aux | grep "src.mcp_server"
```
