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
| [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) | **Complete production deployment guide** | DevOps |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Basic deployment options | DevOps |
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
| [BUG_FIX_HISTORY.md](BUG_FIX_HISTORY.md) | **Complete bug fix record (66 bugs fixed)** | ✅ Current |
| [PRODUCTION_READY_FINAL_REPORT.md](PRODUCTION_READY_FINAL_REPORT.md) | Production readiness assessment | ✅ Current |

**Key Achievements:**
- ✅ 66 bugs fixed (17 Critical, 29 High, 20 Medium)
- ✅ 11 dedicated fix commits
- ✅ 176 tests added (91% pass rate)
- ✅ Production readiness: 62% → 92%

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

### Current Status: 92% Production Ready ✅

**✅ Complete:**
- Security (95%) - WebSocket auth, input validation, rate limiting
- Functionality (100%) - All core features working
- Process Monitoring (95%) - Real-time tracking
- State Management (100%) - Fixed state bleed issues
- Backtesting (100%) - Cost model fixed, tests passing
- Documentation (100%) - Comprehensive guides complete

**⚠️ For 100% Production Ready:**
- Test Coverage - 75% current, target 80% (1 week)
- Performance Testing - Load testing needed (1 week)
- Monitoring Dashboard - Prometheus + Grafana (2 weeks)

**Ready for:** ✅ Beta/Staging Deployment

See: [PRODUCTION_READY_FINAL_REPORT.md](PRODUCTION_READY_FINAL_REPORT.md) for complete assessment

---

## 🗂️ Documentation by Topic

### By Use Case

**I want to...**
- **Get started quickly** → [QUICKSTART.md](QUICKSTART.md)
- **Train a model** → [README.md](README.md) + `scripts/train_sample_model.py`
- **Run backtests** → [README.md](README.md) + `scripts/run_backtest.py`
- **Deploy to production** → [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) ⭐
- **Use MCP server** → [MCP_SETUP.md](MCP_SETUP.md)
- **Secure WebSockets** → [WEBSOCKET_SECURITY.md](WEBSOCKET_SECURITY.md)
- **Fix backtesting costs** → [COST_MIGRATION_GUIDE.md](COST_MIGRATION_GUIDE.md)
- **Understand architecture** → [PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md)
- **Debug issues** → [BUG_FIX_HISTORY.md](BUG_FIX_HISTORY.md)

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
- [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) - Complete production guide ⭐
- [DEPLOYMENT.md](DEPLOYMENT.md) - Basic deployment
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
- **Bug Fix History**: [BUG_FIX_HISTORY.md](BUG_FIX_HISTORY.md)
- **Production Status**: [PRODUCTION_READY_FINAL_REPORT.md](PRODUCTION_READY_FINAL_REPORT.md)

---

## 📅 Documentation Versions

**Current Version:** v2.0.0 (October 7, 2025)

**Recent Updates:**
- Oct 11, 2025: Consolidated bug fix documentation
- Oct 7, 2025: Comprehensive audit consolidation
- Oct 7, 2025: Security features documented
- Oct 7, 2025: Process monitoring documented
- Oct 7, 2025: WebSocket authentication guide

**Historical Documentation:** See `/docs/archive/` for archived documentation and lessons learned.

---

## 📂 Additional Documentation Resources

### Configuration & Reference Documents

| Document | Description | Purpose |
|----------|-------------|---------|
| [DELIVERY_SUMMARY.md](DELIVERY_SUMMARY.md) | Complete delivery inventory | What's included in platform |
| [PORT_CONFIGURATION.md](PORT_CONFIGURATION.md) | Port configuration guide | Port management |
| [PORTS_UPDATED.md](PORTS_UPDATED.md) | Port update summary | Port changes |
| [CLAUDE_MCP_CONFIGS.md](CLAUDE_MCP_CONFIGS.md) | Claude MCP config examples | MCP setup |
| [MCP_DEBUG_GUIDE.md](MCP_DEBUG_GUIDE.md) | MCP debugging guide | Troubleshooting |
| [CLAUDE.md](CLAUDE.md) | Project instructions for Claude | Development guidelines |

### Test & Validation Reports

| Document | Description | Status |
|----------|-------------|--------|
| [COMPREHENSIVE_E2E_TEST_REPORT.md](COMPREHENSIVE_E2E_TEST_REPORT.md) | End-to-end test report | ✅ Complete |
| [API_INTEGRATION_TEST_REPORT.md](API_INTEGRATION_TEST_REPORT.md) | API integration tests | ✅ Complete |
| [API_TEST_SUMMARY.md](API_TEST_SUMMARY.md) | API test summary | ✅ Complete |
| [API_TESTING_CHECKLIST.md](API_TESTING_CHECKLIST.md) | API testing checklist | ✅ Complete |
| [PROCESSMONITOR_TEST_REPORT.md](PROCESSMONITOR_TEST_REPORT.md) | ProcessMonitor tests | ✅ Complete |
| [TEST_FIXING_PROGRESS.md](TEST_FIXING_PROGRESS.md) | Test fixing progress | ✅ Complete |
| [VALIDATION_REPORT.md](VALIDATION_REPORT.md) | System validation report | ✅ Complete |
| [VALIDATION_SUMMARY.md](VALIDATION_SUMMARY.md) | Validation summary | ✅ Complete |
| [VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md) | Validation checklist | ✅ Complete |

### Bug Fix & Issue Reports

| Document | Description | Status |
|----------|-------------|--------|
| [BUG_FIXES_SUMMARY.md](BUG_FIXES_SUMMARY.md) | Summary of all bug fixes | ✅ Complete |
| [BUGS_QUICK_REFERENCE.md](BUGS_QUICK_REFERENCE.md) | ProcessMonitor bugs | ✅ Fixed |
| [PROCESSMONITOR_BUG_FIXES_COMPLETE.md](PROCESSMONITOR_BUG_FIXES_COMPLETE.md) | ProcessMonitor bug fixes | ✅ Complete |
| [PROCESSMONITOR_BUGS_QUICK_REF.md](PROCESSMONITOR_BUGS_QUICK_REF.md) | Quick reference | ✅ Complete |
| [TASK_CANCELLATION_FIX_REPORT.md](TASK_CANCELLATION_FIX_REPORT.md) | Task cancellation fix | ✅ Complete |
| [DEBUGGING_SUMMARY.md](DEBUGGING_SUMMARY.md) | Debugging workflows | Reference |

### Configuration Fix Reports

| Document | Description | Status |
|----------|-------------|--------|
| [CONFIGURATION_FIXES_SUMMARY.md](CONFIGURATION_FIXES_SUMMARY.md) | Configuration fixes | ✅ Complete |
| [CONFIGURATION_FIXES_VERIFICATION.md](CONFIGURATION_FIXES_VERIFICATION.md) | Configuration verification | ✅ Verified |

### Cost Model Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [QLIB_COST_CONFIGURATION_RESEARCH.md](QLIB_COST_CONFIGURATION_RESEARCH.md) | Cost model research | ✅ Complete |
| [COST_MIGRATION_GUIDE.md](COST_MIGRATION_GUIDE.md) | Cost implementation guide | ✅ Complete |
| [COST_FIX_VERIFICATION.md](COST_FIX_VERIFICATION.md) | Cost fix verification | ✅ Verified |
| [COST_MODEL_IMPLEMENTATION_SUMMARY.md](COST_MODEL_IMPLEMENTATION_SUMMARY.md) | Cost model summary | ✅ Complete |

### UI/UX Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [UI_CRITICAL_FIXES_IMPLEMENTATION.md](UI_CRITICAL_FIXES_IMPLEMENTATION.md) | Critical UI fixes | ✅ Complete |
| [UI_UX_BUG_VERIFICATION_REPORT.md](UI_UX_BUG_VERIFICATION_REPORT.md) | UI/UX bug verification | ✅ Complete |
| [UX_IMPROVEMENTS_IMPLEMENTATION.md](UX_IMPROVEMENTS_IMPLEMENTATION.md) | UX improvements | ✅ Complete |
| [UX_IMPROVEMENTS_SUMMARY.md](UX_IMPROVEMENTS_SUMMARY.md) | UX improvements summary | ✅ Complete |

### WebSocket Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [WEBSOCKET_ISSUES_SUMMARY.md](WEBSOCKET_ISSUES_SUMMARY.md) | WebSocket issues | ✅ Resolved |
| [WEBSOCKET_EDGE_CASE_FIXES.md](WEBSOCKET_EDGE_CASE_FIXES.md) | Edge case fixes | ✅ Complete |

### Gap Analysis & Completion Reports

| Document | Description | Status |
|----------|-------------|--------|
| [ALL_GAPS_FIXED_FINAL_REPORT.md](ALL_GAPS_FIXED_FINAL_REPORT.md) | Final gap analysis | ✅ Complete |
| [CURRENT_STATE_VS_SUMMARY_REPORT.md](CURRENT_STATE_VS_SUMMARY_REPORT.md) | State comparison report | ✅ Complete |
| [COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md](COMPREHENSIVE_AUDIT_AND_FIXES_REPORT.md) | Master audit & fixes | ✅ Complete |
| [DATA_PIPELINE_VALIDATION_SUMMARY.md](DATA_PIPELINE_VALIDATION_SUMMARY.md) | Data pipeline validation | ✅ Complete |
| [DOCUMENTATION_UPDATE_SUMMARY.md](DOCUMENTATION_UPDATE_SUMMARY.md) | Documentation updates | ✅ Complete |
| [STATE_BLEED_FIX_REPORT.md](STATE_BLEED_FIX_REPORT.md) | State bleed fix details | ✅ Complete |

---

## 📁 Documentation in /docs Directory

### Active Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [docs/UI_DOCUMENTATION.md](docs/UI_DOCUMENTATION.md) | UI/UX documentation | ✅ Current |
| [docs/MCP_CONFIGURATION.md](docs/MCP_CONFIGURATION.md) | MCP configuration guide | ✅ Current |
| [docs/DOCUMENTATION_MAP.md](docs/DOCUMENTATION_MAP.md) | Documentation organization | ✅ Current |

### Consolidation & Cleanup Reports

| Document | Description | Purpose |
|----------|-------------|---------|
| [docs/ARCHIVE_REPORT.md](docs/ARCHIVE_REPORT.md) | Archive organization report | Cleanup tracking |
| [docs/CONTENT_COVERAGE_VALIDATION.md](docs/CONTENT_COVERAGE_VALIDATION.md) | Content coverage validation | Quality assurance |
| [docs/FILES_TO_DELETE.md](docs/FILES_TO_DELETE.md) | Files marked for deletion | Cleanup tracking |
| [docs/SAFE_TO_DELETE.md](docs/SAFE_TO_DELETE.md) | Safe deletion candidates | Cleanup tracking |
| [docs/ORPHANED_CONTENT.md](docs/ORPHANED_CONTENT.md) | Orphaned content analysis | Quality assurance |
| [docs/LINK_VALIDATION_REPORT.md](docs/LINK_VALIDATION_REPORT.md) | Link validation results | Quality assurance |
| [docs/LINK_VALIDATION_SUMMARY.md](docs/LINK_VALIDATION_SUMMARY.md) | Link validation summary | Quality assurance |
| [docs/MCP_CONSOLIDATION_REPORT.md](docs/MCP_CONSOLIDATION_REPORT.md) | MCP docs consolidation | Cleanup tracking |
| [docs/UI_CONSOLIDATION_REPORT.md](docs/UI_CONSOLIDATION_REPORT.md) | UI docs consolidation | Cleanup tracking |
| [docs/METRICS_CORRECTIONS_REPORT.md](docs/METRICS_CORRECTIONS_REPORT.md) | Metrics corrections | Quality assurance |
| [docs/VALIDATION_SUMMARY.md](docs/VALIDATION_SUMMARY.md) | Validation summary | Quality assurance |

---

## 🗄️ Archive Section

### Historical Documentation

All historical documentation is preserved in `/docs/archive/` for reference.

**Archive Structure:**
```
docs/archive/
├── README.md - Archive overview
├── INDEX.md - Detailed catalog
├── 2024-10/ - October 2024 archives
│   ├── Status reports
│   ├── Configuration updates
│   └── Historical learnings
└── audit-reports-2025-10-07/ - October 7, 2025 audit reports
    ├── Component-specific audits
    └── Deep analysis reports
```

**Key Archive Documents:**
- [docs/archive/README.md](docs/archive/README.md) - How to use the archive
- [docs/archive/INDEX.md](docs/archive/INDEX.md) - Complete archive catalog
- [docs/ARCHIVE_REPORT.md](docs/ARCHIVE_REPORT.md) - What was archived and why

**Archive Categories:**
- ✅ Audit reports from October 7, 2025 (9 documents)
- ✅ Status reports from October 2024 (13 documents)
- ✅ Historical learnings and insights
- ✅ Configuration migration records
- ✅ Debugging iterations

**⚠️ Important:** Archived documents are for historical reference only. Always use current documentation in the root directory for implementation.

---

## 📊 Documentation Statistics

**Total Documentation:** ~17,500 words across all .md files (verified Oct 7, 2025)

**Root Directory:** 49 markdown files
- Getting Started: 4 files (README, QUICKSTART, PLATFORM_OVERVIEW, DELIVERY_SUMMARY)
- Core Documentation: 6 files
- Security: 1 file (WEBSOCKET_SECURITY)
- Configuration: 6 files
- Bug Reports & Fixes: 6 files
- Test Reports: 9 files
- Cost Model: 4 files
- UI/UX: 4 files
- WebSocket: 2 files
- Gap Analysis: 6 files
- MCP: 3 files

**Docs Directory:** 14 markdown files
- Active documentation: 3 files
- Consolidation reports: 11 files

**Archive:** 2 directories with historical content
- October 2024: 13 documents
- October 2025 audits: 9 documents

---

**Last Updated:** October 11, 2025
**Platform Version:** 2.0.0
**Production Readiness:** 92%
**Documentation Completeness:** 100%
