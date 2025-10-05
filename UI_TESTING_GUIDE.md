# 🧪 Real-Time UI Testing Guide

Complete guide to testing the live WebSocket dashboard and ensuring MCP-UI integration works correctly.

## Quick Test (5 Minutes)

### 1. Start the Enhanced Server

```bash
make api-live
# Or: ./scripts/start_server_enhanced.sh
```

You should see:
```
╔════════════════════════════════════════════════════════════════╗
║   Qlib Crypto Trading Platform - Enhanced Live Dashboard      ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting enhanced API server with real-time updates...

📊 Dashboard:     http://localhost:5100
📖 API Docs:      http://localhost:5100/docs
🔌 WebSocket:     ws://localhost:5100/ws/events
```

### 2. Open the Dashboard

Navigate to `http://localhost:5100` in your browser.

**Expected:**
- ✅ Dashboard loads with gradient background
- ✅ Connection status shows "Connected" (green)
- ✅ Statistics cards display (may be 0 initially)
- ✅ Activity feed says "No activity yet"
- ✅ Toast notification appears: "Connected - Real-time updates active"

### 3. Test WebSocket Connection

Open browser console (F12) and check for:
```
Received: {type: 'history', events: [...]}
```

**If you see errors:**
- Check server is running on port 5100
- Verify no firewall blocking WebSocket
- Try refreshing the page

### 4. Trigger an Event via API

In a new terminal:

```bash
curl -X POST http://localhost:5100/api/data/convert \
  -H "Content-Type: application/json" \
  -d '{"dataset": "test", "freq": "1d"}'
```

**Expected in UI:**
- ✅ Activity feed shows new event
- ✅ Toast notification appears
- ✅ Event includes timestamp
- ✅ Animation slides in from left

### 5. Test MCP Integration

**Option A: Using curl to simulate MCP**

```bash
# This simulates what happens when MCP calls a tool
curl -X GET "http://localhost:5100/api/market-data/quote/BTC%2FUSDT"
```

**Option B: Using actual MCP client (Claude Desktop)**

1. Configure MCP server in Claude Desktop (see mcp_config.json)
2. Ask Claude: "Get a quote for BTC/USDT"
3. Watch dashboard update in real-time

**Expected in UI:**
- ✅ Activity feed shows "MCP: market_data_get_quote"
- ✅ Event details show the result
- ✅ Toast notification confirms success
- ✅ Statistics update if relevant

## Comprehensive Testing

### Test 1: Connection Management

**Test automatic reconnection:**

1. Dashboard open and connected
2. Stop server (Ctrl+C)
3. Watch connection status turn red
4. See toast: "Disconnected - Reconnecting..."
5. Restart server
6. Connection should auto-reconnect (green)
7. Toast: "Connected - Real-time updates active"

**Pass Criteria:**
- [ ] Status indicator updates correctly
- [ ] Automatic reconnection works
- [ ] No manual refresh needed

### Test 2: Activity Feed

**Test event ordering and display:**

```bash
# Send multiple events quickly
for i in {1..5}; do
  curl -X GET "http://localhost:5100/api/health" &
done
```

**Expected:**
- [ ] Events appear in chronological order (newest first)
- [ ] Each event has unique timestamp
- [ ] Smooth scroll animation
- [ ] Feed auto-scrolls to top

**Test event persistence:**

1. Generate 60+ events (more than the 50-event limit)
2. Verify only last 50 are kept
3. Oldest events are pruned

### Test 3: Statistics Updates

**Test live statistics:**

```bash
# Create a model (will update stats)
curl -X POST http://localhost:5100/api/models/train \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "crypto",
    "model_handler": "lightgbm",
    "feature_handler": "alpha158"
  }'
```

**Expected:**
- [ ] "Models Trained" counter increments
- [ ] Stats refresh every 5 seconds
- [ ] WebSocket clients count accurate

### Test 4: Toast Notifications

**Test all notification levels:**

```bash
# Success (via successful API call)
curl -X GET "http://localhost:5100/api/health"

# Error (via invalid request)
curl -X POST http://localhost:5100/api/data/convert \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}'
```

**Expected:**
- [ ] Toast slides in from right
- [ ] Correct color for level (green/red/yellow/blue)
- [ ] Auto-dismisses after 5 seconds
- [ ] Multiple toasts stack vertically

### Test 5: Real-Time Model Tracking

**Test model updates:**

```bash
# Train a model
curl -X POST http://localhost:5100/api/models/train \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "crypto",
    "model_handler": "lightgbm"
  }'
```

**Watch for:**
- [ ] "Starting model training" notification
- [ ] Activity feed shows progress
- [ ] Model appears in "Recent Models" sidebar
- [ ] Final "completed" notification

### Test 6: Backtest Progress

**Test backtest tracking:**

```bash
# Run backtest (requires existing model)
curl -X POST http://localhost:5100/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "your_model_id",
    "dataset": "crypto",
    "costs": "medium",
    "rebalance": "weekly"
  }'
```

**Expected:**
- [ ] Progress updates in activity feed
- [ ] Metrics displayed when complete
- [ ] Backtest count increments

### Test 7: Prediction Updates

**Test prediction display:**

```bash
# Generate predictions
curl -X POST http://localhost:5100/api/predictions/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "your_model_id",
    "dataset": "crypto"
  }'
```

**Expected:**
- [ ] Predictions appear in sidebar
- [ ] Top 10 signals shown
- [ ] Scores and ranks displayed
- [ ] Predictions counter updates

### Test 8: Multiple Clients

**Test multi-client broadcasting:**

1. Open dashboard in Browser 1
2. Open dashboard in Browser 2
3. Trigger event via API
4. Both browsers should update simultaneously

**Expected:**
- [ ] Both clients receive same events
- [ ] WebSocket client count shows 2
- [ ] No interference between clients

### Test 9: Browser Console

**Check for errors:**

Open browser console (F12) and verify:

```javascript
// Should see WebSocket messages
Received: {type: "...", data: {...}}

// Should see pong responses
Received: {type: "pong"}

// Should NOT see errors like:
❌ WebSocket connection failed
❌ Cannot read property of undefined
❌ CORS errors
```

### Test 10: Mobile Responsiveness

**Test on mobile device or resize browser:**

1. Resize browser to mobile width (< 768px)
2. Verify layout adjusts
3. Check all elements are accessible
4. Test scrolling on mobile

**Expected:**
- [ ] Dashboard grid stacks vertically
- [ ] Cards remain readable
- [ ] WebSocket still works
- [ ] Touch interactions work

## Performance Testing

### Load Test

**Test with high event volume:**

```bash
# Generate 100 events
for i in {1..100}; do
  curl -X GET "http://localhost:5100/api/health" &
done
```

**Monitor:**
- [ ] UI remains responsive
- [ ] No memory leaks (check browser memory)
- [ ] Events pruned correctly (max 50)
- [ ] No WebSocket disconnections

### Long-Running Connection

**Test WebSocket stability:**

1. Open dashboard
2. Leave for 1+ hour
3. Trigger event
4. Verify still receiving updates

**Expected:**
- [ ] Connection maintained
- [ ] Keep-alive working (30s pings)
- [ ] Events still received
- [ ] No reconnection needed

## Debugging Common Issues

### Issue: WebSocket Won't Connect

**Symptoms:**
- Status shows "Disconnected"
- Console error: `WebSocket connection failed`

**Solutions:**
1. Check server is running: `ps aux | grep uvicorn`
2. Verify port: `lsof -i :5100`
3. Check firewall: `sudo ufw status`
4. Try different browser
5. Check CORS settings in `api_enhanced.py`

### Issue: Events Not Appearing

**Symptoms:**
- WebSocket connected but no events in feed
- Activity feed stays empty

**Solutions:**
1. Check browser console for JavaScript errors
2. Verify event broadcaster is initialized
3. Check `HAS_BROADCASTER` in MCP server
4. Try triggering manual event:
```bash
curl -X GET "http://localhost:5100/api/health"
```

### Issue: UI Not Updating

**Symptoms:**
- Stats not refreshing
- Old data shown

**Solutions:**
1. Hard refresh browser (Ctrl+Shift+R)
2. Clear browser cache
3. Check WebSocket connection status
4. Verify API endpoint accessibility

### Issue: Toast Spam

**Symptoms:**
- Too many toast notifications
- Notifications overlap

**Solutions:**
1. Check event frequency
2. Increase auto-dismiss time in code
3. Filter duplicate notifications
4. Implement toast queue

## Automated Testing Script

Save as `test_ui.sh`:

```bash
#!/bin/bash

echo "🧪 Testing Qlib Real-Time UI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check server
echo "1. Checking server..."
if curl -s http://localhost:5100/api/health > /dev/null; then
    echo "   ✅ Server is running"
else
    echo "   ❌ Server not responding"
    exit 1
fi

# Check WebSocket
echo "2. Testing WebSocket..."
# (Would need wscat or similar)

# Trigger events
echo "3. Triggering test events..."
curl -s -X GET "http://localhost:5100/api/health" > /dev/null
echo "   ✅ Health check sent"

# Check stats
echo "4. Checking stats endpoint..."
curl -s -X GET "http://localhost:5100/api/system/stats" | jq '.'
echo "   ✅ Stats retrieved"

echo ""
echo "✅ All tests passed!"
echo "Open http://localhost:5100 to see live updates"
```

## Success Criteria Checklist

### Basic Functionality
- [ ] Dashboard loads without errors
- [ ] WebSocket connects automatically
- [ ] Connection status accurate
- [ ] Events appear in feed
- [ ] Toast notifications work
- [ ] Statistics update

### Real-Time Features
- [ ] MCP tool calls visible immediately
- [ ] Model training progress tracked
- [ ] Backtest updates shown live
- [ ] Predictions display correctly
- [ ] All event types handled

### Reliability
- [ ] Automatic reconnection works
- [ ] No memory leaks
- [ ] Performance acceptable under load
- [ ] Multi-client support
- [ ] Long-running stability

### UX/UI
- [ ] Smooth animations
- [ ] Responsive design
- [ ] Clear visual hierarchy
- [ ] Intuitive navigation
- [ ] No console errors

## Next Steps After Testing

If all tests pass:
1. ✅ UI is production-ready
2. ✅ Can demonstrate to users
3. ✅ Ready for real workflows

If tests fail:
1. Review error logs
2. Check this debugging guide
3. Fix issues incrementally
4. Retest

---

**The real-time UI should feel instant, responsive, and reliable. Every MCP action should be immediately visible in the dashboard.** 🎯
