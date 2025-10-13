# MCP Server Manual Verification Scripts

This directory contains manual verification scripts for the MCP server's stdio transport layer.

## Scripts

### verify_stdio.py

Manual test for MCP server stdio communication. This script:
- Starts the MCP server as a subprocess
- Sends JSON-RPC messages via stdin
- Reads responses from stdout
- Verifies the stdio transport works correctly

**Usage:**
```bash
python scripts/mcp_verification/verify_stdio.py
```

**Note:** This is NOT a pytest test because it:
- Starts subprocess at module level
- Requires interactive/manual verification
- Tests stdio transport specifically (covered by other integration tests)

## Pytest Tests

Automated MCP tests are in `tests/test_mcp_*.py`:
- `test_mcp_init.py` - Server initialization
- `test_mcp_state_isolation.py` - State isolation between requests
- `test_mcp_protocol.py` - Protocol handshake and API calls
- `test_mcp_list_tools.py` - Tools listing functionality

Run with:
```bash
make test-mcp
```
