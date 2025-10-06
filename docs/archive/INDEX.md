# Documentation Archive Index

This directory contains historical documentation that was accurate at the time of writing but has been superseded by current documentation.

## Archive Purpose

- **Historical Reference**: Understanding past decisions and context
- **Debugging Legacy Issues**: Reference for troubleshooting
- **Learning from Experience**: Document evolution and lessons learned
- **NOT for Current Development**: Use README.md and PLATFORM_OVERVIEW.md instead

---

## October 2024 - State Bleed Fix & System Audit

Archive Date: **2024-10-07**

### Category 1: Status Reports (Time-Sensitive)

#### CURRENT_STATUS.md
- **Date**: 2024-10-06
- **Archived Reason**: Time-sensitive status report from mid-development
- **Content Summary**:
  - Development goal: Sharpe >2.0, MaxDD <15%
  - Infrastructure 100% complete (28/28 tests passing)
  - Qlib data conversion issues identified
  - 366 days BTC data ready
- **Current Alternative**: See README.md "Features" section and PLATFORM_OVERVIEW.md
- **Key Takeaways**:
  - Platform infrastructure was solid from day 1
  - Data pipeline needed official Qlib converter (now implemented)

#### SOLUTION_PLAN.md
- **Date**: 2024-10-06
- **Archived Reason**: Planning document for issues that have been resolved
- **Content Summary**:
  - 3 parallel tracks: Fix Qlib data, get more data, direct CSV training
  - Detailed implementation timeline (4-6 hours estimated)
  - Success metrics defined
- **Current Alternative**: Issues resolved, no alternative needed
- **Key Takeaways**:
  - Track 1 succeeded: Official Qlib converter now works
  - Track 2 completed: Full year data available
  - Systematic debugging approach paid off

#### TEST_RESULTS.md
- **Date**: 2024-10-06
- **Archived Reason**: Test results from specific point in time
- **Content Summary**:
  - End-to-end pipeline test results
  - Download: ✅ PASS (366 days)
  - Conversion: ✅ PASS (official dump_bin.py)
  - Training: ✅ PASS (LightGBM)
  - Backtest: ❌ FAIL (serialization error - later fixed)
- **Current Alternative**: Run `pytest` for current test status
- **Key Takeaways**:
  - Calendar naming is critical (day.txt not 1d.txt)
  - Always specify date ranges in D.features()
  - Process monitoring provides excellent visibility

#### AUDIT_REPORT.md
- **Date**: 2024-10-06
- **Archived Reason**: Audit of specific code state (issues now fixed)
- **Content Summary**:
  - Found 2 critical violations: backtest fallback, old converter usage
  - Both fixed and removed
  - No hardcoded test data confirmed
- **Current Alternative**: Code is clean, no audit needed
- **Key Takeaways**:
  - Fail-fast is better than fallbacks for debugging
  - Official tools should always be preferred
  - Comprehensive audits catch hidden issues

#### CLEANUP_REPORT.md
- **Date**: 2024-10-06
- **Archived Reason**: Cleanup actions completed
- **Content Summary**:
  - Removed 5 dead code items
  - Deprecated old converter and API
  - Removed broken UI files
  - 54 lines of dead code removed
- **Current Alternative**: Code is clean
- **Key Takeaways**:
  - Keep historical files as .deprecated rather than deleting
  - Dead code hides bugs and confuses developers
  - Regular cleanup improves code quality

#### TESTING_VERIFICATION.md
- **Date**: 2024-10-06
- **Archived Reason**: Verification of specific fix (state bleed)
- **Content Summary**:
  - State bleed fix verification
  - All unit tests passing
  - Direct functional tests passing
  - MCP server state isolation working
- **Current Alternative**: State bleed fixed, see STATE_BLEED_FIX.md for implementation
- **Key Takeaways**:
  - qlib.data.cache.H must be cleared between inits
  - Functional tests simulating real usage are valuable
  - Comprehensive testing builds confidence

---

### Category 2: Historical Records

#### LEARNINGS.md
- **Date**: 2024-10-06
- **Archived Reason**: Historical learnings incorporated into current docs
- **Content Summary**:
  - Qlib binary format is optimal (27x faster, 84x less space)
  - Binary format requirements documented
  - Instruments file must use actual date ranges
  - UX improvements: merged Market Data sections
- **Current Alternative**: Technical details in STATE_BLEED_FIX.md and PLATFORM_OVERVIEW.md
- **Key Takeaways**:
  - File system beats database for sequential backtesting
  - Test-driven approach catches issues early
  - Should use official tools from the start

#### CRYPTO_TRADING_GOAL.md
- **Date**: 2024-10-06
- **Archived Reason**: Superseded by README.md goals section
- **Content Summary**:
  - Goal: Sharpe >2.0, MaxDD <15%
  - Research-based configurations
  - Precision-tuned hyperparameters
  - 9 ML models ready
- **Current Alternative**: README.md "Features" and PLATFORM_OVERVIEW.md
- **Key Takeaways**:
  - Research-based approach: LSTM 3.23 Sharpe, LightGBM #1 for BTC
  - Crypto needs 24/7 calendar and specific tuning
  - Transaction costs must be realistic (0.1% per trade)

#### STATE_BLEED_SOLUTION_SUMMARY.md
- **Date**: 2024-10-06
- **Archived Reason**: Short summary superseded by detailed STATE_BLEED_FIX.md
- **Content Summary**:
  - Root cause: qlib.data.cache.H persists across inits
  - Solution: Clear cache before each init
  - Implementation: src/utils/qlib_state.py
- **Current Alternative**: STATE_BLEED_FIX.md (kept - comprehensive guide)
- **Key Takeaways**:
  - qlib.init() doesn't clear cache automatically
  - MCP server needs clean state per tool call
  - Simple solution: clear_qlib_cache() + init_qlib_clean()

---

### Category 3: Configuration Updates (Completed)

#### PORTS_UPDATED.md
- **Date**: 2024-10-06
- **Archived Reason**: Port migration complete, now documented in PORT_CONFIGURATION.md
- **Content Summary**:
  - Changed from 8000 → 5100 (API)
  - Changed from 5432 → 5110 (PostgreSQL)
  - Changed from 6379 → 5120 (Redis)
  - Updated 15 files
- **Current Alternative**: PORT_CONFIGURATION.md (kept - comprehensive reference)
- **Key Takeaways**:
  - 5100 series avoids common development port conflicts
  - Environment variables provide override flexibility
  - Comprehensive updates prevent broken references

#### MCP_CONFIG_FIXED.md
- **Date**: 2024-10-06
- **Archived Reason**: Debugging iteration superseded by MCP_SETUP.md
- **Content Summary**:
  - Required `args` field for Claude Code
  - Bash wrapper for debug logging
  - Python direct invocation options
- **Current Alternative**: MCP_SETUP.md (canonical reference)
- **Key Takeaways**: MCP client requirements vary, test configurations

#### MCP_CONFIG_WITH_STDERR.md
- **Date**: 2024-10-06
- **Archived Reason**: Debugging iteration superseded by MCP_SETUP.md
- **Content Summary**:
  - stderr capture for debugging
  - Log file monitoring approach
  - Shell wrapper for error capture
- **Current Alternative**: MCP_SETUP.md + MCP_DEBUG_GUIDE.md
- **Key Takeaways**: Debugging MCP servers requires stderr visibility

#### MCP_CONFIG_FINAL.md
- **Date**: 2024-10-06
- **Archived Reason**: Debugging iteration superseded by MCP_SETUP.md
- **Content Summary**:
  - Full Python path to venv
  - Resolved PATH issues
  - Simplified vs complex configs
- **Current Alternative**: MCP_SETUP.md (canonical reference)
- **Key Takeaways**: Use virtual environment Python directly to avoid PATH issues

---

## How to Use This Archive

### ✅ Good Uses
1. **Understanding Historical Context**: "Why was this decision made?"
2. **Debugging Legacy Issues**: "What was the original implementation?"
3. **Learning from Past Challenges**: "How did we solve similar problems?"
4. **Tracking Evolution**: "How did the codebase improve over time?"

### ❌ Bad Uses
1. **Current Development Reference**: Use README.md and PLATFORM_OVERVIEW.md instead
2. **Copy-Paste Code**: Archived code may have bugs or use deprecated patterns
3. **Feature Implementation**: Use current best practices, not historical snapshots

---

## Archive Organization

```
docs/archive/
├── INDEX.md (this file)
├── 2024-10/
│   ├── Status Reports (6 files)
│   │   ├── CURRENT_STATUS.md
│   │   ├── SOLUTION_PLAN.md
│   │   ├── TEST_RESULTS.md
│   │   ├── AUDIT_REPORT.md
│   │   ├── CLEANUP_REPORT.md
│   │   └── TESTING_VERIFICATION.md
│   ├── Historical Records (3 files)
│   │   ├── LEARNINGS.md
│   │   ├── CRYPTO_TRADING_GOAL.md
│   │   └── STATE_BLEED_SOLUTION_SUMMARY.md
│   └── Configuration Updates (4 files)
│       ├── PORTS_UPDATED.md
│       ├── MCP_CONFIG_FIXED.md
│       ├── MCP_CONFIG_WITH_STDERR.md
│       └── MCP_CONFIG_FINAL.md
└── [future archives]/
```

**Total Archived**: 13 files from October 2024

---

## Key Insights Extracted from Archive

### Development Process Wins ✅
1. **Test-Driven Development**: 28/28 tests passing before feature development
2. **Fail-Fast Philosophy**: Remove fallbacks, surface errors immediately
3. **Official Tools First**: Use Qlib's dump_bin.py, not custom converters
4. **Comprehensive Audits**: Regular code audits catch hidden issues
5. **Documentation Evolution**: Consolidate scattered docs into cohesive guides

### Technical Wins ✅
1. **State Management**: Clear qlib cache between MCP tool calls
2. **Calendar Naming**: Qlib expects "day.txt" not "1d.txt"
3. **Data Format**: Official Qlib binary format is optimal for backtesting
4. **Process Monitoring**: Real-time visibility improves debugging
5. **Port Configuration**: 5100 series avoids conflicts

### Lessons Learned 💡
1. **Start with Official Tools**: Custom implementations often have subtle bugs
2. **Test State Isolation Early**: Global state bleeds are hard to debug
3. **Document Decisions**: Future you will thank present you
4. **Clean Code Regularly**: Dead code hides bugs and confuses developers
5. **Consolidate Docs**: Multiple scattered docs create confusion

---

## Current Documentation Structure

Use these for active development:

### Primary Documentation
- **README.md**: Quick start, features, API examples
- **PLATFORM_OVERVIEW.md**: Architecture, components, technical details
- **QUICKSTART.md**: Fast setup and first run
- **DEPLOYMENT.md**: Production deployment guide

### Technical Guides
- **STATE_BLEED_FIX.md**: State management implementation (KEEP)
- **PORT_CONFIGURATION.md**: Port reference (KEEP)
- **UI_FEATURES.md**: Web interface features
- **UI_TESTING_GUIDE.md**: UI testing procedures

### MCP Documentation
- **MCP_SETUP.md**: MCP server configuration
- **MCP_DEBUG_GUIDE.md**: Debugging MCP issues
- **CLAUDE_MCP_CONFIGS.md**: Claude Desktop integration

---

## Archive Maintenance

### When to Archive
- ✅ Time-sensitive status reports (quarterly or after major milestones)
- ✅ Completed solution plans
- ✅ Historical test results
- ✅ Superseded documentation
- ✅ Completed migration reports

### When to Keep Active
- ✅ Living documentation (README, PLATFORM_OVERVIEW)
- ✅ Technical reference guides (STATE_BLEED_FIX, PORT_CONFIGURATION)
- ✅ Setup and deployment guides
- ✅ Current best practices

### Archive Review
- Review archive annually
- Consolidate related archives
- Delete truly obsolete content (ask first!)
- Update this index with new insights

---

## Questions About Archived Content?

If you're referencing archived content and need clarification:

1. **Check current docs first**: The answer may be in README.md or PLATFORM_OVERVIEW.md
2. **Check git history**: `git log --follow docs/archive/2024-10/FILE.md`
3. **Ask the team**: Archived decisions may have context not captured in docs

---

**Archive Created**: 2024-10-07
**Last Updated**: 2024-10-07
**Maintained By**: Development Team
