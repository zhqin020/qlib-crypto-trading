# Documentation Index

**Qlib Crypto Trading Platform v2.0.0** - Complete documentation map and quick reference guide.

---

## 🚀 Getting Started

**New users start here:**

1. **[README.md](README.md)** - Project overview, features, installation
2. **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
3. **[PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md)** - Architecture and capabilities

**Estimated Time to First Model:** 15 minutes

---

## 📚 Core Documentation

### Installation & Setup

| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](README.md) | Complete project documentation | All users |
| [QUICKSTART.md](QUICKSTART.md) | Fast setup (5 minutes) | New users |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guide | DevOps |
| [MCP_SETUP.md](MCP_SETUP.md) | MCP server configuration | MCP users |
| [.env.example](.env.example) | Environment configuration template | All users |

### Platform Features

| Document | Description | Topics |
|----------|-------------|--------|
| [PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md) | Architecture and features | Data, models, backtesting, serving |
| [STATE_BLEED_FIX.md](STATE_BLEED_FIX.md) | State management technical details | Qlib initialization, testing |

### Security & Authentication

| Document | Description | Critical Info |
|----------|-------------|---------------|
| [WEBSOCKET_SECURITY.md](WEBSOCKET_SECURITY.md) | **WebSocket authentication guide** | API keys, rate limits, connection security |
| README.md - Security Section | Overview of security features | Authentication, validation, limits |

**Key Commands:**
```bash
# Generate API key
python3 -c "from src.ui.security import generate_api_key; print(generate_api_key())"

# Add to .env
WEBSOCKET_API_KEYS=your_generated_key_here
```

---

## 🔧 Technical Guides

### Data Pipeline

| Document | Description | Use Case |
|----------|-------------|----------|
| [DATA_PIPELINE_VALIDATION_SUMMARY.md](DATA_PIPELINE_VALIDATION_SUMMARY.md) | Input validation implementation | Security, data integrity |

**Key Scripts:**
- `scripts/download_sample_data.py` - Download crypto data
- `scripts/convert_to_qlib.py` - Convert CSV to Qlib format

### Model Training

| Document | Description | Use Case |
|----------|-------------|----------|
| README.md - Supported Models | LightGBM, XGBoost, LSTM, Transformer | Model selection |

**Key Scripts:**
- `scripts/train_sample_model.py` - Train default model
- `scripts/train_crypto_models.py` - Multi-crypto training
- `scripts/train_multi_crypto.py` - Advanced training scenarios

### Backtesting

| Document | Description | Status |
|----------|-------------|--------|
| [QLIB_COST_CONFIGURATION_RESEARCH.md](QLIB_COST_CONFIGURATION_RESEARCH.md) | Cost model research | Research complete |
| [COST_MIGRATION_GUIDE.md](COST_MIGRATION_GUIDE.md) | Cost implementation guide | Implementation pending |

**Key Scripts:**
- `scripts/run_backtest.py <model_id>` - Run backtest

⚠️ **Important:** Cost model implementation is pending. Current results may be 20-40% too optimistic.

### Serving & Predictions

**Key Scripts:**
- `scripts/predict.py <model_id>` - Generate predictions

---

## 🔌 API Documentation

### REST API

**Interactive Documentation:**
- **Swagger UI**: http://localhost:5100/docs
- **OpenAPI Spec**: http://localhost:5100/openapi.json

**Key Endpoints:**
- `GET /api/health` - Health check
- `POST /api/models/train` - Train model
- `POST /api/backtests/run` - Run backtest
- `POST /api/predictions/generate` - Generate predictions
- `GET /api/processes` - List all processes
- `DELETE /api/processes/{id}` - Cancel process

### WebSocket API

| Endpoint | Description | Authentication |
|----------|-------------|----------------|
| `/ws/events` | Platform-wide events | Required |
| `/ws/processes` | All process updates | Required |
| `/ws/processes/{id}` | Specific process updates | Required |
| `/ws/market-data` | Real-time market quotes | Required |

**Authentication:** API key via header or query parameter

See: [WEBSOCKET_SECURITY.md](WEBSOCKET_SECURITY.md)

### MCP Tools

**15 Available Tools:**

**Data Management:**
- `data_create_snapshot` - Build dataset
- `features_create_set` - Create feature configuration
- `market_data_get_quote` - Get quote
- `market_data_get_quotes_batch` - Batch quotes
- `market_data_get_historical` - Historical OHLCV
- `market_data_subscribe` - Real-time updates

**Model Training:**
- `models_train` - Train ML model
- `experiments_run_recipe` - Run experiment
- `experiments_tag` - Tag experiments
- `runs_cancel` - Cancel job

**Backtesting & Serving:**
- `backtests_run` - Run backtest
- `serving_predict_today` - Generate predictions
- `notifications_dispatch` - Send notifications
- `schedules_create` - Schedule jobs

**Knowledge Base:**
- `knowledge_describe_screen` - UI screen descriptions

See: [MCP_SETUP.md](MCP_SETUP.md)

---

## 🐛 Troubleshooting & Reference

### Bug Reports & Fixes

| Document | Description | Status |
|----------|-------------|--------|
| [COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md](COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md) | **Master audit & fixes report** | ✅ Current |
| [BUGS_QUICK_REFERENCE.md](BUGS_QUICK_REFERENCE.md) | ProcessMonitor bugs | ✅ Fixed |
| [DEBUGGING_SUMMARY.md](DEBUGGING_SUMMARY.md) | Debugging workflows | Reference |

### Audit Reports (Historical)

**⚠️ Note:** Most individual audit reports have been superseded by the comprehensive report above.

| Document | Component | Date | Status |
|----------|-----------|------|--------|
| COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md | **All components** | Oct 7, 2025 | ✅ Current |
| CODEBASE_DEEP_SCAN_MASTER_REPORT.md | All | Oct 7, 2025 | Consolidated |
| CRITICAL_FIXES_COMPLETE_REPORT.md | Fixes | Oct 7, 2025 | Consolidated |
| API_ENHANCED_AUDIT_REPORT.md | API | Oct 7, 2025 | Consolidated |
| PROCESSMONITOR_DEEP_DEBUG_ANALYSIS.md | Monitoring | Oct 7, 2025 | Consolidated |
| UI_COMPREHENSIVE_AUDIT_REPORT.md | UI/UX | Oct 7, 2025 | Consolidated |
| WEBSOCKET_EDGE_CASE_ANALYSIS.md | WebSockets | Oct 7, 2025 | Consolidated |
| DATA_PIPELINE_AUDIT_REPORT.md | Data | Oct 7, 2025 | Consolidated |
| TRAINER_BUGS_ANALYSIS.md | Training | Oct 7, 2025 | Consolidated |
| BACKTESTING_ENGINE_AUDIT_REPORT.md | Backtesting | Oct 7, 2025 | Consolidated |

**Use the comprehensive report for the complete picture.**

### Common Issues

**"No module named 'qlib'"**
```bash
pip install pyqlib
```

**"WebSocket connection failed"**
- Check WEBSOCKET_API_KEYS in .env
- Verify API key is valid
- Check API server is running

**"Dataset not found"**
```bash
# Run conversion
python scripts/convert_to_qlib.py
```

**"Process cancelled unexpectedly"**
- Check process logs: `GET /api/processes/{id}/logs`
- Review server logs for errors

---

## 📊 Production Readiness

### Current Status: 92% Production Ready

**✅ Complete:**
- Security (95%) - WebSocket auth, input validation, rate limiting
- Functionality (95%) - All core features working
- Process Monitoring (95%) - Real-time tracking
- State Management (90%) - Fixed state bleed issues

**⚠️ Pending:**
- Backtesting Cost Model - Research complete, implementation pending (4 hours)
- Test Coverage - 67% current, target 80% (70 hours)
- Documentation - Main docs updated, API reference pending (6 hours)

See: [COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md](COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md) Section: "Production Readiness Assessment"

---

## 🗂️ Documentation by Topic

### By Use Case

**I want to...**
- **Get started quickly** → [QUICKSTART.md](QUICKSTART.md)
- **Train a model** → [README.md](README.md) + `scripts/train_sample_model.py`
- **Run backtests** → [README.md](README.md) + `scripts/run_backtest.py`
- **Deploy to production** → [DEPLOYMENT.md](DEPLOYMENT.md)
- **Use MCP server** → [MCP_SETUP.md](MCP_SETUP.md)
- **Secure WebSockets** → [WEBSOCKET_SECURITY.md](WEBSOCKET_SECURITY.md)
- **Fix backtesting costs** → [COST_MIGRATION_GUIDE.md](COST_MIGRATION_GUIDE.md)
- **Understand architecture** → [PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md)
- **Debug issues** → [COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md](COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md)

### By Role

**Data Scientists:**
- [QUICKSTART.md](QUICKSTART.md) - Fast setup
- [README.md](README.md) - Model training, backtesting
- [PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md) - Features

**Developers:**
- [README.md](README.md) - API documentation
- [STATE_BLEED_FIX.md](STATE_BLEED_FIX.md) - Technical implementation
- [WEBSOCKET_SECURITY.md](WEBSOCKET_SECURITY.md) - Security implementation
- http://localhost:5100/docs - Interactive API docs

**DevOps Engineers:**
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
- [.env.example](.env.example) - Configuration
- [WEBSOCKET_SECURITY.md](WEBSOCKET_SECURITY.md) - Security setup

**MCP Users:**
- [MCP_SETUP.md](MCP_SETUP.md) - Complete MCP guide
- [README.md](README.md) - MCP tools list

---

## 📝 Quick Command Reference

### Setup
```bash
pip install -r requirements.txt
make setup
python3 -c "from src.ui.security import generate_api_key; print('WEBSOCKET_API_KEYS=' + generate_api_key())" >> .env
```

### Data Pipeline
```bash
make download-data      # Download sample data
make convert            # Convert to Qlib format
```

### Training & Testing
```bash
make train                                  # Train default model
python scripts/run_backtest.py <model_id>  # Backtest model
python scripts/predict.py <model_id>       # Generate predictions
```

### Services
```bash
make api                # Start API server (localhost:5100)
make mcp                # Start MCP server
make docker-up          # Start all services with Docker
```

### Testing
```bash
make test               # Run all tests
pytest tests/ -v        # Verbose test output
```

---

## 🔗 External Resources

- **Microsoft Qlib**: https://github.com/microsoft/qlib
- **CCXT**: https://github.com/ccxt/ccxt
- **MCP Protocol**: https://modelcontextprotocol.io
- **FastAPI Docs**: https://fastapi.tiangolo.com

---

## 📞 Support

- **Issues**: GitHub Issues
- **API Docs**: http://localhost:5100/docs (when server running)
- **Audit Reports**: [COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md](COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md)

---

## 📅 Documentation Versions

**Current Version:** v2.0.0 (October 7, 2025)

**Recent Updates:**
- Oct 7, 2025: Comprehensive audit consolidation
- Oct 7, 2025: Security features documented
- Oct 7, 2025: Process monitoring documented
- Oct 7, 2025: WebSocket authentication guide

**Historical Documentation:** See `/docs/archive/` for archived documentation and lessons learned.

---

**Last Updated:** October 7, 2025
**Platform Version:** 2.0.0
**Production Readiness:** 92%
