# 🚀 Qlib Crypto Trading Platform

A comprehensive AI-powered cryptocurrency trading and research platform built on Microsoft's Qlib framework with full MCP (Model Context Protocol) server integration.

## ✨ Features

### 🎯 Core Capabilities
- **Multi-Exchange Data Acquisition**: Binance, Kraken, Coinbase support via CCXT
- **24/7 Crypto Calendar**: Custom calendar supporting continuous cryptocurrency trading
- **Advanced ML Models**: LightGBM, XGBoost, LSTM, Transformer models
- **Comprehensive Backtesting**: Crypto-specific metrics including funding rates
- **Real-Time Predictions**: Generate daily trading signals
- **MCP Server Integration**: Full control via MCP client interface
- **Web Dashboard**: Beautiful UI for monitoring and control
- **REST API**: Complete FastAPI-based API with WebSocket support

### 📊 Supported Models
- **LightGBM**: Fast gradient boosting (default)
- **XGBoost**: Alternative gradient boosting
- **LSTM**: Recurrent neural networks for time series
- **Transformer**: Attention-based models for market dynamics

### 💹 Feature Engineering
- **Alpha158**: 158 technical indicators for daily trading
- **Alpha360**: 360 features for intraday trading
- **Custom Features**: Extensible feature engineering pipeline

## 🏗️ Architecture

```
qlib-2/
├── src/
│   ├── mcp_server/          # MCP server implementation
│   ├── data_pipeline/       # Data acquisition & processing
│   ├── models/              # Model training & experiments
│   ├── backtesting/         # Backtesting engine
│   ├── serving/             # Real-time serving & predictions
│   └── ui/                  # Web UI & REST API
├── config/                  # Configuration files
├── data/                    # Data storage
│   ├── raw/                 # Raw CSV data
│   ├── qlib/                # Qlib binary format
│   └── processed/           # Processed data
├── models/trained/          # Trained models
├── backtests/              # Backtest results
├── predictions/            # Daily predictions
├── experiments/            # Experiment tracking
├── scripts/                # Utility scripts
└── docker-compose.yml      # Docker deployment
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Docker & Docker Compose (optional)
- 4GB+ RAM
- 10GB+ disk space

### Installation

#### Option 1: Local Installation
```bash
# Clone repository
git clone <repository-url>
cd qlib-2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p data/{raw,qlib,processed} models/trained backtests predictions experiments logs
```

#### Option 2: Docker
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

### Basic Usage

#### 1. Download Sample Data
```bash
python scripts/download_sample_data.py
```

This downloads historical data for top 10 cryptocurrencies (BTC, ETH, BNB, etc.) from 2023-2024.

#### 2. Convert to Qlib Format
```bash
python scripts/convert_to_qlib.py
```

Converts CSV data to Qlib's optimized binary format with 24/7 crypto calendar.

#### 3. Train a Model
```bash
python scripts/train_sample_model.py
```

Trains a LightGBM model with Alpha158 features.

#### 4. Run Backtest
```bash
python scripts/run_backtest.py <model_id>
```

Evaluates model performance with crypto-specific metrics.

#### 5. Generate Predictions
```bash
python scripts/predict.py <model_id>
```

Generates trading signals for today's session.

## 🌐 Web Interface

Start the API server:
```bash
# Using script
./scripts/start_server.sh

# Or directly
python -m uvicorn src.ui.api_enhanced:app --host 0.0.0.0 --port 5100 --reload
```

Access:
- **Dashboard**: http://localhost:5100
- **API Docs**: http://localhost:5100/docs
- **OpenAPI**: http://localhost:5100/openapi.json

## 🔌 MCP Server

The platform includes a full MCP server for programmatic control.

### Starting the MCP Server
```bash
./scripts/start_mcp_server.sh
```

### MCP Server Configuration

Add to your MCP client config (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/qlib-2",
      "env": {
        "PYTHONPATH": "/path/to/qlib-2/src"
      }
    }
  }
}
```

### Available MCP Tools

#### Data Management
- `data_create_snapshot`: Build dataset snapshot
- `features_create_set`: Create feature configuration
- `market_data_get_quote`: Get real-time quote
- `market_data_get_quotes_batch`: Get multiple quotes
- `market_data_get_historical`: Get historical OHLCV data
- `market_data_subscribe`: Subscribe to real-time updates

#### Model Training
- `models_train`: Train ML model
- `experiments_run_recipe`: Execute experiment recipe
- `experiments_tag`: Tag experiment runs
- `runs_cancel`: Cancel running job

#### Backtesting
- `backtests_run`: Run backtest with trained model

#### Serving
- `serving_predict_today`: Generate daily predictions
- `notifications_dispatch`: Send notifications
- `schedules_create`: Create scheduled jobs

### Example MCP Usage

```python
# Using MCP client
import mcp

client = mcp.Client("qlib-trading")

# Download historical data
result = await client.call_tool(
    "market_data_get_historical",
    {
        "symbol": "BTC/USDT",
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
        "interval": "1d"
    }
)

# Train model
result = await client.call_tool(
    "models_train",
    {
        "dataset_ref": "crypto",
        "feature_set_ref": "alpha158_crypto",
        "handler": "lightgbm"
    }
)

# Generate predictions
result = await client.call_tool(
    "serving_predict_today",
    {
        "model_id": "lightgbm_20241006_123456_abc123",
        "dataset_ref": "crypto"
    }
)
```

## 📡 REST API Examples

### Get Real-Time Quote
```bash
curl http://localhost:5100/api/market-data/quote/BTC/USDT
```

### Download Data
```bash
curl -X POST http://localhost:5100/api/data/download \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "start_date": "2023-01-01",
    "end_date": "2024-12-31",
    "interval": "1d"
  }'
```

### Train Model
```bash
curl -X POST http://localhost:5100/api/models/train \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "crypto",
    "feature_handler": "alpha158",
    "model_handler": "lightgbm"
  }'
```

### Run Backtest
```bash
curl -X POST http://localhost:5100/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "lightgbm_20241006_123456",
    "dataset": "crypto",
    "costs": "medium",
    "rebalance": "weekly"
  }'
```

## 🧪 Experiment Recipes

Pre-configured experiment workflows:

- **beginner_lightgbm**: Simple LightGBM with Alpha158
- **beginner_xgboost**: XGBoost with Alpha158
- **advanced_lstm**: LSTM for time series prediction
- **advanced_transformer**: Transformer with attention
- **expert_ensemble**: Multiple models ensemble
- **intraday_alpha360**: High-frequency trading with Alpha360

Run via API:
```bash
curl -X POST http://localhost:5100/api/experiments/run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "crypto",
    "recipe": "beginner_lightgbm",
    "costs": "medium",
    "rebalance": "weekly"
  }'
```

## 📊 Performance Metrics

The platform calculates crypto-specific metrics:

- **Annualized Return**: Adjusted for 365-day trading
- **Sharpe Ratio**: Risk-adjusted returns (24/7 volatility)
- **Sortino Ratio**: Downside risk focus
- **Max Drawdown**: Largest peak-to-trough decline
- **Calmar Ratio**: Return/Drawdown ratio
- **Information Ratio**: Excess return consistency
- **Win Rate**: Percentage of profitable periods

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# API
API_HOST=0.0.0.0
API_PORT=5100

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost:5110/qlib_crypto

# Exchange API Keys (for authenticated endpoints)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### Custom Feature Sets

Create custom features in `config/features/`:

```json
{
  "name": "custom_features",
  "handler": "Alpha158",
  "config": {
    "class": "Alpha158",
    "kwargs": {
      "infer_processors": [
        {"class": "RobustZScoreNorm", "kwargs": {"clip_outlier": true}},
        {"class": "Fillna"}
      ],
      "label": ["Ref($close, -1) / $close - 1"]
    }
  }
}
```

## 🐳 Docker Deployment

### Full Stack Deployment
```bash
docker-compose up -d
```

This starts:
- API server (port 5100)
- MCP server
- PostgreSQL (port 5110)
- Redis (port 5120)

### Individual Services
```bash
# API only
docker-compose up -d api

# MCP server only
docker-compose up -d mcp-server
```

## 📈 Monitoring & Alerts

### Notifications

Configure notifications in `.env`:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

Send notifications via API:
```bash
curl -X POST http://localhost:5100/api/notifications/send \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "prediction_ready",
    "channels": ["slack", "console"],
    "payload": {
      "model_id": "lightgbm_123",
      "top_signals": "BTC, ETH, SOL"
    }
  }'
```

### Scheduled Jobs

Create recurring jobs using RRULE:

```python
# Daily predictions at 9 AM
await create_schedule(
    job="generate_predictions",
    rrule="FREQ=DAILY;BYHOUR=9",
    params={"model_id": "lightgbm_123", "dataset_ref": "crypto"}
)
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_data_pipeline.py

# With coverage
pytest --cov=src tests/
```

## 📚 Advanced Usage

### State Management

The platform automatically manages Qlib state to prevent data contamination:

- **Automatic calendar registration**: 24/7 crypto calendar is registered automatically
- **Cache clearing**: Qlib cache is cleared before each initialization
- **Concurrency protection**: Async lock prevents race conditions
- **Clean initialization**: Each tool call starts with fresh state

```python
from utils.qlib_state import init_qlib_clean

# For synchronous contexts
success = init_qlib_clean(provider_uri="/path/to/data", region="cn")

# For async contexts (MCP tools)
from utils.qlib_state import init_qlib_clean_async
success = await init_qlib_clean_async(provider_uri="/path/to/data", region="cn")
```

See [STATE_BLEED_FIX.md](STATE_BLEED_FIX.md) for technical details.

### Custom Data Handler

```python
from qlib.data.dataset.handler import DataHandlerLP
from utils.qlib_state import init_qlib_clean

class CryptoHandler(DataHandlerLP):
    def __init__(self, instruments="all", **kwargs):
        super().__init__(instruments=instruments, **kwargs)

    # Custom data processing
    def process(self, data):
        # Add crypto-specific features
        data['funding_rate'] = calculate_funding_rate(data)
        return data
```

### Custom Model

```python
from qlib.contrib.model.base import Model
from utils.qlib_state import init_qlib_clean

class CustomCryptoModel(Model):
    def fit(self, dataset):
        # Initialize with clean state
        init_qlib_clean(provider_uri="data/qlib/crypto", region="cn")
        # Custom training logic
        pass

    def predict(self, dataset):
        # Custom prediction logic
        pass
```

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

- Built on [Microsoft Qlib](https://github.com/microsoft/qlib)
- Exchange data via [CCXT](https://github.com/ccxt/ccxt)
- MCP protocol by [Anthropic](https://modelcontextprotocol.io)

## 🆘 Support

- Issues: https://github.com/your-repo/qlib-2/issues
- Documentation: See `/docs` directory
- API Docs: http://localhost:5100/docs
- Historical Documentation: See `/docs/archive/` for development history and lessons learned

## 🗺️ Roadmap

- [ ] Multi-asset portfolio optimization
- [ ] Real-time order execution
- [ ] Advanced risk management
- [ ] More ML models (GNN, Reinforcement Learning)
- [ ] Cloud deployment templates
- [ ] Mobile app integration

---

**⚠️ Disclaimer**: This platform is for research and educational purposes. Cryptocurrency trading involves substantial risk of loss. Always do your own research and never invest more than you can afford to lose.
