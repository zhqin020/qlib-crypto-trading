# MCP Server Debug Guide

## Updated MCP Configuration with Logging

Use this configuration in Claude Code to enable backend logging:

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

## Where to Find Backend Logs

**Log file location**: `/tmp/mcp_server.log`

To watch logs in real-time while adding the server to Claude:

```bash
tail -f /tmp/mcp_server.log
```

## What You Should See in the Logs

When Claude Code connects to the MCP server, you should see:

```
2025-10-06 11:42:06,106 - __main__ - INFO - __main__ starting...
2025-10-06 11:42:06,106 - __main__ - INFO - MCP Server starting...
2025-10-06 11:42:06,106 - __main__ - INFO - Python version: 3.13.3...
2025-10-06 11:42:06,106 - __main__ - INFO - Creating stdio server...
2025-10-06 11:42:06,111 - __main__ - INFO - Stdio server created, creating initialization options...
2025-10-06 11:42:06,113 - __main__ - INFO - Initialization options: server_name='qlib-crypto-trading'...
2025-10-06 11:42:06,113 - __main__ - INFO - Starting server.run()...
```

If the server is waiting for Claude's initialize request, you'll see the logs stop at "Starting server.run()..." - this is normal.

## Debugging Steps

1. **Open a terminal and start watching logs**:
   ```bash
   tail -f /tmp/mcp_server.log
   ```

2. **Add the MCP server in Claude Code** using the config above

3. **Check what appears in the log file**:
   - If you see "MCP Server starting..." → Server launched successfully
   - If you see "Creating stdio server..." → Server reached the stdio setup
   - If you see "Starting server.run()..." → Server is waiting for Claude's initialize request
   - If you see nothing → Server didn't start (Claude might not be launching it)

4. **Check Claude Code's MCP logs**:
   - Open Claude Code settings
   - Navigate to MCP Servers section
   - Look for error messages or connection status

## If Server Still Doesn't Work

If you see logs appearing but Claude still shows "infinite loading":

1. **Check if Claude is sending the initialize request** - The log should show activity after "Starting server.run()..."

2. **Verify the server responds** - Run this test independently:
   ```bash
   python test_mcp_init.py
   ```
   This should complete in ~0.4 seconds.

3. **Check Claude Code version** - Ensure you're using the latest version that supports MCP protocol version 2024-11-05

4. **Try direct Python command** - Replace the shell script with direct Python:
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
   Then check `/tmp/mcp_server.log` - if it's empty, add `2>> /tmp/mcp_server.log` won't work with this format.

## Expected Timeline

Based on testing:
- Server startup: ~1.3 seconds (import time)
- Initialize response: ~0.4 seconds
- Total: ~1.7 seconds

If Claude shows loading for more than 5 seconds, something is wrong - check the logs!
