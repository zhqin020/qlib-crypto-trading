# WebSocket Authentication and Security

## Overview

All WebSocket endpoints in `/src/ui/api_enhanced.py` are now secured with API key authentication and comprehensive security features.

## Authentication Strategy

**API Key Based Authentication** (simple, pragmatic approach)
- API keys passed via Authorization header or query parameter
- Keys validated before accepting WebSocket connection
- Unauthorized connections rejected with 401/403

## Secured Endpoints

All 4 WebSocket endpoints are now protected:

1. **`/ws/events`** - Real-time platform events
2. **`/ws/processes`** - All process updates
3. **`/ws/processes/{id}`** - Specific process updates
4. **`/ws/market-data`** - Real-time market data

## Security Features

### 1. Authentication
- **API Key Validation**: Keys validated from `WEBSOCKET_API_KEYS` environment variable
- **Two Methods**:
  - Header: `Authorization: Bearer <api_key>`
  - Query Parameter: `?api_key=<api_key>`
- **Failed Attempt Tracking**: Max 5 failed attempts per IP in 5 minutes

### 2. Connection Limits
- **Max 10 concurrent connections per user**
- Connections tracked by user ID (derived from API key)
- 11th connection rejected with policy violation

### 3. Rate Limiting
- **Max 100 messages per minute per connection**
- Sliding window rate limiting
- Exceeded limits return error message

### 4. Message Size Limits
- **Max 1MB per message**
- Oversized messages rejected with error
- Prevents memory exhaustion attacks

### 5. Heartbeat Timeout
- **60 second timeout** without activity
- Connections automatically closed if inactive
- Prevents zombie connections

## Configuration

Add to `.env` file:

```bash
# WebSocket Security Configuration
WEBSOCKET_API_KEYS=key1,key2,key3  # Comma-separated

# Optional limits (defaults shown)
WS_MAX_MESSAGE_SIZE=1048576       # 1MB
WS_MAX_CONNECTIONS_PER_USER=10
WS_MAX_MESSAGES_PER_MINUTE=100
WS_HEARTBEAT_TIMEOUT=60
```

## Generating API Keys

```python
python3 -c "from src.ui.security import generate_api_key; print(generate_api_key())"
```

Example output: `qlib_A7xK9mP2nQ8vB5tR4wL6cF1yH3jD0sE`

## Client Usage

### Method 1: Query Parameter

```javascript
const ws = new WebSocket('ws://localhost:5100/ws/events?api_key=YOUR_API_KEY');
```

### Method 2: Authorization Header

```python
import websockets

headers = {"Authorization": "Bearer YOUR_API_KEY"}
async with websockets.connect('ws://localhost:5100/ws/events', extra_headers=headers) as ws:
    await ws.send(json.dumps({"type": "ping"}))
    response = await ws.recv()
```

### Method 3: cURL

```bash
curl -N \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:5100/ws/events
```

## Error Responses

### Authentication Failed (401/403)
```json
{
  "detail": "Authentication required. Provide API key in Authorization header or api_key query parameter."
}
```
Connection closed with code 1008 (Policy Violation)

### Connection Limit Exceeded
```json
{
  "detail": "Maximum 10 concurrent connections per user"
}
```
Connection closed with code 1008

### Rate Limit Exceeded
```json
{
  "type": "error",
  "message": "Rate limit exceeded. Max 100 messages per minute."
}
```

### Message Too Large
```json
{
  "type": "error",
  "message": "Message exceeds maximum size of 1048576 bytes"
}
```

## Security Module

Location: `/src/ui/security.py`

Key components:
- `authenticate_websocket()` - Validates API key from connection
- `ConnectionManager` - Tracks connections, rate limits, heartbeats
- `validate_api_key()` - Validates API key against allowed keys
- `check_message_size()` - Validates message size
- `generate_api_key()` - Generates secure random keys

## Testing

Run the test suite:

```bash
# Start the server first
python3 -m src.ui.api_enhanced

# In another terminal
pytest tests/test_websocket_auth.py -v
```

Tests cover:
- ✓ No authentication (rejected)
- ✓ Invalid API key (rejected)
- ✓ Valid API key via query param (accepted)
- ✓ Valid API key via header (accepted)
- ✓ Message size limits
- ✓ Rate limiting
- ✓ Connection limits
- ✓ API key generation

## Production Deployment

### 1. Generate Production Keys

```bash
python3 -c "from src.ui.security import generate_api_key; print(generate_api_key())"
```

### 2. Set Environment Variables

```bash
export WEBSOCKET_API_KEYS="qlib_prod_key_1,qlib_prod_key_2"
```

### 3. Distribute Keys Securely
- Never commit keys to version control
- Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate keys periodically
- Provide different keys to different clients for tracking

### 4. Monitor
- Log failed authentication attempts
- Track connection counts per user
- Monitor rate limit violations
- Set up alerts for suspicious patterns

## Security Best Practices

1. **Key Rotation**: Rotate keys every 90 days
2. **Key Distribution**: Use secure channels (never email/Slack)
3. **Per-Client Keys**: Issue unique keys to each client
4. **Monitoring**: Log all authentication events
5. **Rate Limiting**: Adjust limits based on legitimate usage patterns
6. **TLS**: Use WSS (secure WebSocket) in production
7. **Firewall**: Restrict WebSocket access by IP if possible

## Implementation Details

### Connection Flow

```
1. Client connects with API key
2. Server validates key
3. Server checks connection limit
4. Server adds connection to tracking
5. Server accepts connection
6. Client sends messages
7. Server checks message size
8. Server checks rate limit
9. Server updates heartbeat
10. Server processes message
```

### Error Handling

- Authentication errors: Close with code 1008
- No information leakage in error messages
- Failed attempts logged for monitoring
- Graceful degradation on errors

### Performance

- O(1) API key validation (set lookup)
- O(1) connection tracking (dict lookup)
- O(n) rate limiting (n = messages in last minute)
- Minimal memory overhead per connection
- Non-blocking async I/O

## Troubleshooting

### Connection Rejected Immediately

**Cause**: Missing or invalid API key
**Solution**: Verify API key is correct and in WEBSOCKET_API_KEYS

### Connection Timeout After 60s

**Cause**: No heartbeat/activity
**Solution**: Send ping messages periodically

### Rate Limit Errors

**Cause**: Sending more than 100 messages/minute
**Solution**: Implement client-side rate limiting

### Connection Limit Reached

**Cause**: Too many concurrent connections from same key
**Solution**: Close unused connections or request more keys

## Files Modified

- `/src/ui/security.py` - New security module
- `/src/ui/api_enhanced.py` - All WebSocket endpoints secured
- `/.env.example` - Added security configuration
- `/tests/test_websocket_auth.py` - Comprehensive test suite

## Summary

All WebSocket endpoints are now production-ready with:
- ✓ API key authentication
- ✓ Connection limits (10 per user)
- ✓ Rate limiting (100 msg/min)
- ✓ Message size limits (1MB)
- ✓ Heartbeat timeouts (60s)
- ✓ Failed attempt tracking
- ✓ Comprehensive error handling
- ✓ No information leakage
- ✓ Full test coverage
