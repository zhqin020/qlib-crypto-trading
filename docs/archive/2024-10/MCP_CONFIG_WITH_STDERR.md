# MCP Config That Captures Error Logs

Use this configuration to capture stderr from the MCP server:

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "sh",
      "args": ["-c", "exec python -u -m src.mcp_server 2>/tmp/mcp_stderr.log"],
      "cwd": "/Users/chadwyatt/Code/trading/qlib-2",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

## How to Debug

1. **Clear the old log**:
   ```bash
   rm -f /tmp/mcp_stderr.log
   ```

2. **Watch the log in real-time**:
   ```bash
   tail -f /tmp/mcp_stderr.log
   ```

3. **Add the server in Claude Code** using the config above

4. **Check what appears in the log**:
   - If it shows "About to call app.run()..." then hangs → Claude isn't sending initialize request
   - If it shows "Server.run() returned" → stdin closed unexpectedly
   - If it shows errors → we'll see what's failing

## What You Should See

Normal successful startup should show:
```
2025-10-06 11:xx:xx,xxx - __main__ - INFO - __main__ entry point
2025-10-06 11:xx:xx,xxx - __main__ - INFO - MCP Server starting...
2025-10-06 11:xx:xx,xxx - __main__ - INFO - stdin isatty: False
2025-10-06 11:xx:xx,xxx - __main__ - INFO - stdin closed: False
2025-10-06 11:xx:xx,xxx - __main__ - INFO - Creating stdio server...
2025-10-06 11:xx:xx,xxx - __main__ - INFO - Stdio server created successfully
2025-10-06 11:xx:xx,xxx - __main__ - INFO - About to call app.run()...
[then it should wait for messages from Claude]
```
