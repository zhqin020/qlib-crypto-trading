# Final MCP Configuration (With Full Python Path)

The issue was that `python` wasn't in PATH. Use the full path to your venv Python:

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "sh",
      "args": ["-c", "exec /Users/chadwyatt/Code/trading/qlib-2/venv/bin/python3 -u -m src.mcp_server 2>/tmp/mcp_stderr.log"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Or simpler version using the venv directly:

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

## To See Logs (if using first config)

```bash
tail -f /tmp/mcp_stderr.log
```

The second config won't capture stderr, but should work if the first one does.
