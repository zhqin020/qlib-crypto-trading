# 🎨 Real-Time UI Features

## Overview

The Qlib Crypto Trading Platform now includes a **fully interactive, real-time dashboard** with WebSocket-based live updates. Every action taken through the MCP server or API is instantly reflected in the UI.

## 🌟 Key Features

### 1. **Real-Time Activity Feed** 📡
- Live stream of all platform events
- MCP tool executions appear instantly
- Color-coded by event type (success, error, warning, info)
- Detailed event data with expandable views
- Automatic scrolling for new events
- Maintains last 50 events in memory

### 2. **Live Statistics Dashboard** 📊
- **Models Trained**: Real-time count updates
- **Backtests**: Live backtest tracking
- **Predictions**: Instant prediction count
- **Active WebSocket Connections**: Current client count

### 3. **WebSocket Event Broadcasting** 🔌
- Bidirectional communication
- Automatic reconnection on disconnect
- Connection status indicator
- Keep-alive ping/pong mechanism
- Event history replay for new connections

### 4. **Toast Notifications** 🔔
- Non-intrusive popup alerts
- Auto-dismiss after 5 seconds
- Styled by severity level
- Smooth slide-in animations

### 5. **Model Tracking** 🤖
- Real-time model status updates
- Live training progress
- Recent models sidebar
- Click to expand details

### 6. **Prediction Visualization** 🔮
- Latest predictions displayed live
- Top signals highlighted
- Real-time score updates
- Symbol rankings

### 7. **Modern, Responsive UI** 📱
- Clean, professional design
- Gradient backgrounds
- Smooth animations
- Mobile-friendly layout
- Dark mode ready

## 🔄 Event Types

### MCP Tool Execution
```json
{
  "type": "mcp_tool_execution",
  "data": {
    "tool": "models_train",
    "arguments": {...},
    "result": {...},
    "status": "success"
  }
}
```

### Data Updates
```json
{
  "type": "data_update",
  "data": {
    "update_type": "download_complete",
    "data": {
      "symbols": ["BTC/USDT", "ETH/USDT"],
      "count": 2
    }
  }
}
```

### Model Updates
```json
{
  "type": "model_update",
  "data": {
    "model_id": "lightgbm_20241006_123456",
    "status": "completed",
    "metrics": {...}
  }
}
```

### Backtest Progress
```json
{
  "type": "backtest_update",
  "data": {
    "model_id": "lightgbm_20241006_123456",
    "progress": 0.75,
    "metrics": {...}
  }
}
```

### Predictions
```json
{
  "type": "prediction_update",
  "data": {
    "model_id": "lightgbm_20241006_123456",
    "predictions": [
      {"symbol": "BTC_USDT", "score": 0.0523, "rank": 1}
    ]
  }
}
```

### Notifications
```json
{
  "type": "notification",
  "data": {
    "level": "success",
    "message": "Model training completed",
    "details": {...}
  }
}
```

## 🚀 Getting Started

### Start the Enhanced Server

```bash
# Using the enhanced startup script
./scripts/start_server_enhanced.sh

# Or directly with uvicorn
python -m uvicorn src.ui.api_enhanced:app --host 0.0.0.0 --port 5100 --reload
```

### Access the Dashboard

```
http://localhost:5100
```

### WebSocket Connection

The UI automatically connects to:
```
ws://localhost:5100/ws/events
```

## 💡 Usage Examples

### Watching MCP Tool Execution

1. Open dashboard: `http://localhost:5100`
2. Use MCP client (Claude Desktop) to call a tool
3. Watch the activity feed update in real-time
4. See toast notification appear
5. View statistics update

### Monitoring Model Training

1. Trigger model training via API or MCP
2. Watch "Models Trained" counter increase
3. See activity feed show progress
4. Receive completion notification
5. New model appears in "Recent Models" sidebar

### Live Backtesting

1. Start backtest via API
2. Watch progress in activity feed
3. See real-time metric updates
4. Completion notification with results
5. Backtest appears in statistics

## 🎨 UI Components

### Connection Status Indicator
- **Green** with pulsing dot: Connected
- **Red** with static dot: Disconnected
- Automatic reconnection attempts

### Activity Feed
- Scrollable list of events
- Newest events at top
- Color-coded borders
- Timestamp display
- Expandable event data

### Statistics Cards
- Hover animation
- Real-time value updates
- Clean typography
- Gradient accents

### Toast Notifications
- Slide-in from right
- Color-coded by level:
  - **Success**: Green
  - **Info**: Blue
  - **Warning**: Yellow
  - **Error**: Red

## 🔧 Technical Details

### Architecture

```
┌─────────────────┐
│  MCP Client     │
│ (Claude Desktop)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│   MCP Server    │◄────►│ Event Broadcaster│
└────────┬────────┘      └────────┬─────────┘
         │                        │
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌──────────────────┐
│   FastAPI       │◄────►│   WebSocket      │
└────────┬────────┘      └────────┬─────────┘
         │                        │
         ▼                        ▼
    REST API              ┌──────────────────┐
                          │   Browser UI     │
                          │  (Vue.js + WS)   │
                          └──────────────────┘
```

### Event Flow

1. **MCP Tool Called** → Tool executes
2. **Result Generated** → Event broadcaster notified
3. **Broadcast to WebSockets** → All connected clients receive event
4. **UI Updates** → Activity feed, stats, toasts update
5. **User Sees** → Real-time reflection of action

### WebSocket Implementation

**Server Side:**
- FastAPI WebSocket endpoint
- Event broadcasting system
- Connection management
- Message routing

**Client Side:**
- Automatic connection on page load
- Reconnection logic
- Event handling
- UI state updates

## 📊 Performance

- **WebSocket Latency**: < 50ms
- **Event Processing**: Real-time
- **UI Updates**: Instant
- **Max Events in Feed**: 50 (auto-pruning)
- **Toast Auto-Dismiss**: 5 seconds
- **Stats Refresh**: Every 5 seconds

## 🎯 Use Cases

### Research & Development
- Monitor long-running training jobs
- Track multiple backtests simultaneously
- Review prediction generation
- Debug data pipeline issues

### Production Monitoring
- Real-time system health
- Active connection tracking
- Error alerting
- Performance metrics

### Demonstration
- Show live ML training
- Demonstrate real-time predictions
- Present system capabilities
- Interactive walkthroughs

## 🔐 Security

- WebSocket connections use same origin policy
- No authentication required for local use
- Add JWT tokens for production deployment
- Rate limiting on WebSocket messages

## 🚧 Future Enhancements

Potential additions:
- [ ] Chart.js integration for live graphs
- [ ] Model performance comparison charts
- [ ] Real-time portfolio value tracking
- [ ] Interactive parameter tuning
- [ ] Multi-user collaboration
- [ ] Export activity log
- [ ] Customizable dashboard layout
- [ ] Dark mode toggle
- [ ] Mobile app companion

## 📝 Code Examples

### Broadcasting Custom Events

```python
from ui.events import get_event_broadcaster

broadcaster = get_event_broadcaster()

await broadcaster.broadcast_notification(
    level="success",
    message="Custom event triggered",
    details={"key": "value"}
)
```

### Listening to Events (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:5100/ws/events');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Event received:', data);
    
    if (data.type === 'mcp_tool_execution') {
        // Handle MCP event
    }
};
```

## 🆘 Troubleshooting

### WebSocket Won't Connect
- Check server is running
- Verify port 5100 is accessible
- Look for CORS issues in browser console
- Check firewall settings

### Events Not Appearing
- Verify MCP server has broadcasting enabled
- Check browser console for errors
- Ensure WebSocket connection is active
- Refresh page to reconnect

### Slow Updates
- Check network latency
- Monitor server load
- Review event broadcast queue
- Consider reducing event frequency

---

**The real-time UI transforms the Qlib platform into an interactive, observable system where every action is instantly visible and traceable.** 🎉
