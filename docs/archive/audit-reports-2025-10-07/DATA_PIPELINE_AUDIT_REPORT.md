# Data Pipeline Audit Report

**Date:** 2025-10-07
**Auditor:** Claude Code
**Scope:** src/data_pipeline/

---

## Executive Summary

This audit examined 7 Python modules in the data pipeline for validation gaps, error handling issues, data integrity problems, edge cases, performance issues, and incomplete features. **35 issues were identified** across all severity levels, with **8 CRITICAL** issues requiring immediate attention.

### Critical Findings Summary
- Missing input validation on user-supplied parameters
- No transaction/rollback mechanisms for data corruption scenarios
- Memory exhaustion risks with large datasets
- Race conditions in concurrent operations
- Missing timezone normalization
- Incomplete error recovery mechanisms

---

## 1. snapshot.py - Point-in-Time Snapshot Creation

### File: `/Users/chadwyatt/Code/trading/qlib-2/src/data_pipeline/snapshot.py`

#### CRITICAL ISSUES

**C1: No Input Validation on User Parameters**
- **Location:** Lines 17-22 (function signature)
- **Issue:** `dataset`, `calendar`, `start`, `end` parameters accept any string without validation
- **Impact:** Can cause crashes, path traversal vulnerabilities, or SQL injection if dataset name is used in queries
- **Example:**
  ```python
  # Malicious inputs not validated:
  create_snapshot("../../etc/passwd", "invalid_calendar", "not-a-date", "garbage")
  ```
- **Fix Required:**
  - Validate dataset name against whitelist/regex pattern
  - Validate calendar name against known calendar types
  - Validate date formats (YYYY-MM-DD) and ranges
  - Sanitize all path inputs

**C2: No Atomicity/Transaction Support**
- **Location:** Lines 52-108 (main conversion logic)
- **Issue:** If conversion fails mid-process, partial files may be left on disk with no cleanup mechanism
- **Impact:** Data corruption, orphaned files, inconsistent state
- **Scenario:**
  - Step 4 (line 73-87) succeeds in converting some CSV files
  - Step 5 (line 90) fails during metadata save
  - Result: Qlib directory has partial data but no metadata
- **Fix Required:**
  - Implement transaction-like behavior with rollback on failure
  - Use temporary directories and atomic moves
  - Add cleanup in exception handler

**C3: Race Condition in Process ID Generation**
- **Location:** Lines 36-37
- **Issue:** While UUID reduces collision risk, the process monitor might reject IDs if called concurrently
- **Impact:** Process tracking failures in high-concurrency environments
- **Fix Required:** Add mutex/lock or use process monitor's ID generation

#### HIGH SEVERITY ISSUES

**H1: Missing Calendar File Validation**
- **Location:** Lines 60-64
- **Issue:** `generate_crypto_calendars()` is called if directory doesn't exist, but success is not verified
- **Impact:** Silent failure if calendar generation fails
- **Fix Required:** Verify calendar files exist after generation

**H2: Incomplete Error Context in Monitoring**
- **Location:** Lines 116-124
- **Issue:** Generic exception handler loses stack trace context for monitoring system
- **Impact:** Difficult to debug failures, poor operational visibility
- **Fix Required:** Include full exception details in `fail_process()` call

**H3: CSV File Existence Not Checked**
- **Location:** Lines 79-87
- **Issue:** Assumes CSV files exist if directory exists, but `list(csv_dir.glob("*.csv"))` could return empty
- **Impact:** Creates snapshot with no data, marked as "ready"
- **Fix Required:** Validate file count before conversion

#### MEDIUM SEVERITY ISSUES

**M1: Hard-coded Default Dates**
- **Location:** Lines 96-97
- **Issue:** Default start "2019-01-01" may not match actual data range
- **Impact:** Metadata inaccuracies
- **Fix Required:** Infer dates from actual data or raise error if not provided

**M2: No Validation of Conversion Result**
- **Location:** Lines 81-87
- **Issue:** `convert_crypto_data_official()` result not validated before being saved
- **Impact:** Success saved even if conversion had warnings/errors
- **Fix Required:** Check result status before marking snapshot as "ready"

#### LOW SEVERITY ISSUES

**L1: Missing Logging for Success Path**
- **Location:** Line 111 (after complete_process)
- **Issue:** No intermediate success logging between progress updates
- **Suggestion:** Add info logs for each major step completion

---

## 2. official_qlib_converter.py - Qlib Data Conversion

### File: `/Users/chadwyatt/Code/trading/qlib-2/src/data_pipeline/official_qlib_converter.py`

#### CRITICAL ISSUES

**C4: No Memory Management for Large Files**
- **Location:** Lines 32, 48
- **Issue:** `pd.read_csv(csv_file)` loads entire file into memory
- **Impact:** Memory exhaustion with large datasets (e.g., 1-minute data for multiple years)
- **Example:** 1 year of 1m data = ~500k rows per symbol. 50 symbols = 25M rows in memory
- **Fix Required:** Use chunked reading with `chunksize` parameter

**C5: Unsafe Symbol Extraction from Filename**
- **Location:** Lines 41-42
- **Issue:** `csv_file.stem.split('_')[0].upper()` assumes specific filename format
- **Impact:** IndexError if filename doesn't match pattern (e.g., "data.csv", "BTC.csv")
- **Fix Required:** Add validation, use regex, or require filename format in docs

**C6: No Datetime Parsing Validation**
- **Location:** Line 45
- **Issue:** `pd.to_datetime(df['datetime'])` will fail silently on invalid formats
- **Impact:** Conversion errors or incorrect dates without clear error messages
- **Fix Required:** Validate datetime format explicitly with try-except and error_bad_lines

#### HIGH SEVERITY ISSUES

**H4: NULL Check Too Late**
- **Location:** Lines 55-57
- **Issue:** NULL check happens after normalization, wasting processing time
- **Impact:** Performance degradation, unclear which original column had NULLs
- **Fix Required:** Validate input data immediately after reading CSV

**H5: Empty Data Detection Incomplete**
- **Location:** Lines 59-60
- **Issue:** Only checks for zero rows, not zero columns or all-NULL columns
- **Impact:** Could create invalid datasets
- **Fix Required:** Add comprehensive empty data checks

**H6: Subprocess Error Handling Insufficient**
- **Location:** Lines 111-130
- **Issue:** Only checks return code, doesn't parse stderr for warnings
- **Impact:** Silent failures or warnings that should be errors
- **Fix Required:** Parse dump_bin.py output for known error patterns

**H7: Missing Output Verification**
- **Location:** Lines 134-142
- **Issue:** Only checks directories exist, not that they contain valid data
- **Impact:** Could report success with empty directories
- **Fix Required:** Verify binary files exist in features/ directory

**H8: Cleanup Failure Not Handled**
- **Location:** Lines 215-217
- **Issue:** `shutil.rmtree(normalized_dir)` can fail, leaving temp files
- **Impact:** Disk space leaks
- **Fix Required:** Wrap in try-except, log warnings on cleanup failure

#### MEDIUM SEVERITY ISSUES

**M3: Hard-coded Frequency Mapping**
- **Location:** Lines 147-159
- **Issue:** Frequency mapping is incomplete and hard-coded
- **Impact:** New frequencies require code changes
- **Fix Required:** Move to configuration file

**M4: Insufficient CSV File Filtering**
- **Location:** Lines 197-199
- **Issue:** Filter logic is weak: `freq.replace("d", "D") in f.name or "1d" in f.name.lower()`
- **Impact:** May include wrong files or miss valid files
- **Fix Required:** Use strict regex pattern matching

**M5: No Progress Reporting**
- **Location:** Lines 28-68 (prepare_normalized_csv loop)
- **Issue:** Long-running operations have no progress indication
- **Impact:** Poor user experience, appears hung
- **Fix Required:** Add progress callbacks or logging

#### LOW SEVERITY ISSUES

**L2: Magic Number for Adjustment Factor**
- **Location:** Line 52
- **Issue:** Hard-coded 1.0 factor without explanation
- **Suggestion:** Add comment explaining crypto doesn't need adjustment factors

**L3: Redundant adjclose Column**
- **Location:** Line 51
- **Issue:** `adjclose = close` is redundant for crypto
- **Suggestion:** Document why Qlib requires this field

---

## 3. market_data.py - Market Data Provider

### File: `/Users/chadwyatt/Code/trading/qlib-2/src/data_pipeline/market_data.py`

#### CRITICAL ISSUES

**C7: Global Mutable State (Exchange Cache)**
- **Location:** Line 16 (`_exchanges: Dict[str, ccxt.Exchange] = {}`)
- **Issue:** Global dictionary shared across all requests, not thread-safe
- **Impact:** Race conditions in concurrent environments, memory leaks if exchanges are never cleared
- **Fix Required:** Use thread-local storage or connection pool with proper locking

**C8: No Rate Limit Handling**
- **Location:** Lines 42-62, 92-139
- **Issue:** While `enableRateLimit=True` is set, there's no handling for rate limit errors
- **Impact:** API bans, failed requests
- **Fix Required:** Implement exponential backoff retry logic for 429 errors

#### HIGH SEVERITY ISSUES

**H9: Missing Symbol Validation**
- **Location:** Lines 30, 72
- **Issue:** Symbol format not validated (should be "BASE/QUOTE")
- **Impact:** Confusing errors from exchange API
- **Fix Required:** Validate symbol format matches exchange requirements

**H10: Date Range Validation Missing**
- **Location:** Lines 72-78 (get_historical parameters)
- **Issue:** No validation that start_date < end_date, or that dates are not in future
- **Impact:** Infinite loops or zero results
- **Fix Required:** Validate date parameters before API calls

**H11: No Timeout Configuration**
- **Location:** Lines 22-26 (exchange initialization)
- **Issue:** No timeout set for HTTP requests
- **Impact:** Hanging requests, poor user experience
- **Fix Required:** Add timeout configuration to exchange initialization

**H12: Batch Quote Error Handling Weak**
- **Location:** Lines 65-69
- **Issue:** Uses `return_exceptions=True` but doesn't filter out exceptions from results
- **Impact:** Returns mix of data and exceptions, caller must handle
- **Fix Required:** Filter exceptions, log errors, return structured error info

#### MEDIUM SEVERITY ISSUES

**M6: Interval Validation Missing**
- **Location:** Line 76
- **Issue:** Interval string not validated against exchange-supported values
- **Impact:** Cryptic errors from exchange
- **Fix Required:** Validate interval against exchange.timeframes

**M7: Data Filtering Logic Flawed**
- **Location:** Line 131
- **Issue:** Uses string comparison `df.index >= start_date` which may not work correctly
- **Impact:** Incorrect date filtering
- **Fix Required:** Convert strings to datetime objects for comparison

**M8: No Data Quality Checks**
- **Location:** Lines 122-128 (DataFrame creation)
- **Issue:** No validation that OHLCV data is valid (e.g., high >= low, volume >= 0)
- **Impact:** Invalid data propagates to models
- **Fix Required:** Add data sanity checks

**M9: Subscribe Function is Stub**
- **Location:** Lines 142-156
- **Issue:** Returns placeholder response, doesn't actually subscribe
- **Impact:** Misleading to users, broken feature
- **Fix Required:** Either implement properly or mark as not implemented

#### LOW SEVERITY ISSUES

**L4: Missing Provider Validation**
- **Location:** Lines 19, 42, 67, 93
- **Issue:** Provider defaults to "binance" but no validation it's valid
- **Suggestion:** Validate against ccxt.exchanges list

**L5: Timestamp Filtering Imprecise**
- **Location:** Lines 104-117
- **Issue:** `current_ts = candles[-1][0] + 1` may miss or duplicate candles at boundaries
- **Suggestion:** Use more precise boundary handling

---

## 4. features.py - Feature Set Creation

### File: `/Users/chadwyatt/Code/trading/qlib-2/src/data_pipeline/features.py`

#### HIGH SEVERITY ISSUES

**H13: Import at End of File**
- **Location:** Lines 137-138
- **Issue:** `import pandas as pd` at end of file instead of top
- **Impact:** Import errors if function called before import line is executed
- **Fix Required:** Move import to top of file (line 5)

**H14: Async Function but No Async Operations**
- **Location:** Lines 70-134
- **Issue:** Function is `async` but contains no `await` statements
- **Impact:** Misleading API, unnecessary overhead
- **Fix Required:** Remove async or add actual async operations

**H15: No Schema Validation for Config**
- **Location:** Lines 94-112
- **Issue:** No validation that config structure matches Qlib expectations
- **Impact:** Runtime errors when Qlib tries to use invalid config
- **Fix Required:** Add schema validation using JSON Schema or Pydantic

#### MEDIUM SEVERITY ISSUES

**M10: Hard-coded Module Path**
- **Location:** Lines 27, 51, 102
- **Issue:** Hard-coded "qlib.contrib.data.handler" may not be correct for all handlers
- **Impact:** Import errors for custom handlers
- **Fix Required:** Make module_path configurable

**M11: Missing Dataset Validation**
- **Location:** Line 71
- **Issue:** `dataset_ref` not validated to exist
- **Impact:** Creates feature set for non-existent dataset
- **Fix Required:** Verify dataset exists before creating feature set

**M12: Processor Merge Logic Unclear**
- **Location:** Lines 110-112
- **Issue:** Completely replaces infer_processors if custom processors provided
- **Impact:** Loses default processors, may break functionality
- **Fix Required:** Support merge/append/replace modes

#### LOW SEVERITY ISSUES

**L6: Missing Type Hints**
- **Location:** Lines 23, 47
- **Issue:** Return type hints missing on config functions
- **Suggestion:** Add proper type hints

**L7: Generic Error Response**
- **Location:** Lines 132-134
- **Issue:** Returns dict with "error" key on failure, inconsistent with success response
- **Suggestion:** Use proper exception or result type

---

## 5. crypto_calendar.py - Calendar Generation

### File: `/Users/chadwyatt/Code/trading/qlib-2/src/data_pipeline/crypto_calendar.py`

#### HIGH SEVERITY ISSUES

**H16: Timezone Ambiguity**
- **Location:** Lines 38-39
- **Issue:** `pd.Timestamp(start_date)` doesn't specify timezone
- **Impact:** Ambiguous timestamps, especially for intraday data
- **Fix Required:** Explicitly use UTC for all crypto data

**H17: Frequency Mapping Incomplete**
- **Location:** Lines 53-61
- **Issue:** Only 5 frequencies mapped, hard-coded
- **Impact:** Runtime errors for other valid frequencies (e.g., 2h, 8h, 30m)
- **Fix Required:** Use pandas frequency parsing

#### MEDIUM SEVERITY ISSUES

**M13: Hard-coded Date Range**
- **Location:** Lines 90-91
- **Issue:** 2019-2024 range hard-coded
- **Impact:** Outdated calendars, manual updates required
- **Fix Required:** Generate dynamically based on data needs

**M14: No Validation of Generated Calendars**
- **Location:** Lines 94-106
- **Issue:** No verification that calendar has expected number of periods
- **Impact:** Silent failures in calendar generation
- **Fix Required:** Validate period count matches expectations

#### LOW SEVERITY ISSUES

**L8: Unused to_qlib_format Method**
- **Location:** Lines 64-71
- **Issue:** Method defined but never used
- **Suggestion:** Use for calendar validation or remove

---

## 6. crypto_calendar_provider.py - Qlib Calendar Provider

### File: `/Users/chadwyatt/Code/trading/qlib-2/src/data_pipeline/crypto_calendar_provider.py`

#### HIGH SEVERITY ISSUES

**H18: Cache Memory Leak**
- **Location:** Lines 28, 51-52
- **Issue:** `_calendar_cache` grows unbounded, never cleared
- **Impact:** Memory exhaustion for long-running processes
- **Fix Required:** Implement LRU cache with size limit

**H19: locate_index Logic Bug**
- **Location:** Lines 108-116
- **Issue:** Loop logic is incorrect: `if ts >= start_time and start_idx == 0` will only match first occurrence
- **Impact:** Wrong indices returned for date ranges
- **Fix Required:** Use binary search or pandas.Index.get_loc()

#### MEDIUM SEVERITY ISSUES

**M15: Inconsistent Frequency Parsing**
- **Location:** Lines 65-83
- **Issue:** Different frequency parsing logic than crypto_calendar.py
- **Impact:** Inconsistent behavior between modules
- **Fix Required:** Centralize frequency parsing logic

**M16: Default Date Range Too Wide**
- **Location:** Lines 55-58
- **Issue:** 2010-2030 range loads unnecessary data
- **Impact:** Memory waste, slow initialization
- **Fix Required:** Use tighter default range or lazy loading

---

## 7. Cross-Module Issues

### Integration Problems

**I1: No Shared Validation Module**
- **Impact:** Each module implements its own validation logic inconsistently
- **Fix Required:** Create shared validation utilities module

**I2: Inconsistent Error Types**
- **Impact:** Callers can't reliably catch specific errors
- **Fix Required:** Define custom exception hierarchy

**I3: No Data Quality Framework**
- **Impact:** Bad data can flow through entire pipeline
- **Fix Required:** Implement data quality checks at each stage

**I4: Missing Pipeline Orchestration**
- **Impact:** No clear entry point or dependency management
- **Fix Required:** Create pipeline coordinator/workflow manager

**I5: No Configuration Management**
- **Impact:** Hard-coded values scattered throughout
- **Fix Required:** Centralized configuration system

---

## Summary by Severity

### Critical (8 issues)
1. **C1:** snapshot.py - No input validation (line 17-22)
2. **C2:** snapshot.py - No atomicity/transaction support (line 52-108)
3. **C3:** snapshot.py - Race condition in process ID (line 36-37)
4. **C4:** official_qlib_converter.py - Memory exhaustion risk (line 32, 48)
5. **C5:** official_qlib_converter.py - Unsafe symbol extraction (line 41-42)
6. **C6:** official_qlib_converter.py - No datetime validation (line 45)
7. **C7:** market_data.py - Thread-unsafe global state (line 16)
8. **C8:** market_data.py - No rate limit handling (line 42-62, 92-139)

### High (19 issues)
- snapshot.py: 3 issues (H1-H3)
- official_qlib_converter.py: 5 issues (H4-H8)
- market_data.py: 4 issues (H9-H12)
- features.py: 3 issues (H13-H15)
- crypto_calendar.py: 2 issues (H16-H17)
- crypto_calendar_provider.py: 2 issues (H18-H19)

### Medium (16 issues)
- snapshot.py: 2 issues (M1-M2)
- official_qlib_converter.py: 3 issues (M3-M5)
- market_data.py: 4 issues (M6-M9)
- features.py: 3 issues (M10-M12)
- crypto_calendar.py: 2 issues (M13-M14)
- crypto_calendar_provider.py: 2 issues (M15-M16)

### Low (8 issues)
- snapshot.py: 1 issue (L1)
- official_qlib_converter.py: 3 issues (L2-L3)
- market_data.py: 2 issues (L4-L5)
- features.py: 2 issues (L6-L7)
- crypto_calendar.py: 1 issue (L8)

### Integration (5 issues)
- Cross-module: 5 issues (I1-I5)

---

## Recommendations Priority

### Immediate (Week 1)
1. Fix C1-C8 (all critical issues)
2. Implement input validation framework (I1)
3. Add transaction/rollback mechanism (C2)
4. Fix thread safety issues (C7)

### Short-term (Week 2-3)
1. Fix H1-H19 (high severity issues)
2. Implement proper error handling (I2)
3. Add data quality checks (I3)
4. Fix memory management issues

### Medium-term (Month 1)
1. Fix M1-M16 (medium severity issues)
2. Implement configuration management (I5)
3. Add comprehensive testing
4. Create pipeline orchestration (I4)

### Long-term (Month 2+)
1. Fix L1-L8 (low severity issues)
2. Performance optimization
3. Documentation improvements
4. Monitoring and observability

---

## Testing Recommendations

1. **Unit Tests Needed:**
   - Input validation edge cases
   - Error handling paths
   - Data quality checks
   - Timezone handling

2. **Integration Tests Needed:**
   - End-to-end pipeline flow
   - Transaction rollback scenarios
   - Concurrent operation stress tests
   - Large dataset handling

3. **Property-Based Tests:**
   - Date range handling
   - Symbol normalization
   - Data conversions

4. **Performance Tests:**
   - Memory usage profiling
   - Large file handling
   - Concurrent request handling

---

## Conclusion

The data pipeline has fundamental architectural issues that need addressing:

1. **Validation gaps** throughout the codebase allow invalid data and parameters
2. **Error handling** is inconsistent and incomplete
3. **Data integrity** mechanisms (transactions, atomicity) are missing
4. **Concurrency safety** is not considered (global state, race conditions)
5. **Performance** risks exist with large datasets (memory exhaustion)
6. **Configuration management** is ad-hoc and hard-coded

**Estimated Effort:** 2-3 weeks for critical fixes, 1-2 months for complete refactoring

**Risk Assessment:** HIGH - Production use without fixes could result in data loss, corruption, or system crashes
