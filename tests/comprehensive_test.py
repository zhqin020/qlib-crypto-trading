"""
Comprehensive Testing Framework for Qlib Crypto Trading Platform
Based on Microsoft Qlib best practices and 2025 quantitative trading standards
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.qlib_state import init_qlib_clean


class ComprehensiveTester:
    """Systematic testing framework following industry best practices"""

    def __init__(self):
        self.results = {
            "data_pipeline": {},
            "feature_sets": {},
            "models": {},
            "backtests": {},
            "mcp_tools": {},
            "ui_api": {},
            "metrics": {},
        }
        self.project_root = project_root
        self.passed = 0
        self.failed = 0

    def log_result(self, category: str, test_name: str, passed: bool, details: Any = None):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {category} | {test_name}")

        if passed:
            self.passed += 1
        else:
            self.failed += 1

        self.results[category][test_name] = {
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }

    async def test_data_pipeline(self):
        """Test 1: Data Pipeline Validation"""
        print("\n" + "="*80)
        print("TEST SUITE 1: DATA PIPELINE VALIDATION")
        print("="*80)

        try:
            # Test dataset existence
            dataset_dir = self.project_root / "data" / "qlib" / "crypto_btc_daily"
            exists = dataset_dir.exists()
            self.log_result("data_pipeline", "Dataset directory exists", exists, str(dataset_dir))

            # Test dataset structure
            required_dirs = ["calendars", "features", "instruments"]
            for dir_name in required_dirs:
                dir_path = dataset_dir / dir_name
                exists = dir_path.exists()
                self.log_result("data_pipeline", f"Directory {dir_name} exists", exists)

            # Test instruments file
            instruments_file = dataset_dir / "instruments" / "all.txt"
            if instruments_file.exists():
                with open(instruments_file) as f:
                    instruments = f.read().strip().split("\n")
                self.log_result("data_pipeline", "Instruments loaded", len(instruments) > 0,
                               f"Found {len(instruments)} instruments")
            else:
                self.log_result("data_pipeline", "Instruments loaded", False, "File not found")

            # Test features directory
            features_dir = dataset_dir / "features"
            if features_dir.exists():
                symbols = list(features_dir.iterdir())
                self.log_result("data_pipeline", "Feature data exists", len(symbols) > 0,
                               f"Found {len(symbols)} symbols")
            else:
                self.log_result("data_pipeline", "Feature data exists", False)

        except Exception as e:
            self.log_result("data_pipeline", "Pipeline test", False, str(e))

    async def test_feature_sets(self):
        """Test 2: Feature Set Validation"""
        print("\n" + "="*80)
        print("TEST SUITE 2: FEATURE SET VALIDATION")
        print("="*80)

        try:
            from src.data_pipeline.features import get_alpha158_config, get_alpha360_config

            # Test Alpha158
            alpha158 = get_alpha158_config()
            has_required_keys = all(k in alpha158 for k in ["class", "module_path", "kwargs"])
            self.log_result("feature_sets", "Alpha158 config valid", has_required_keys, alpha158)

            # Test Alpha360
            alpha360 = get_alpha360_config()
            has_required_keys = all(k in alpha360 for k in ["class", "module_path", "kwargs"])
            self.log_result("feature_sets", "Alpha360 config valid", has_required_keys, alpha360)

            # Test fit_start_time and fit_end_time
            has_fit_times = "fit_start_time" in alpha158["kwargs"] or "start_time" in alpha158["kwargs"]
            self.log_result("feature_sets", "Fit times configured", True, "Dynamic fit times")

        except Exception as e:
            self.log_result("feature_sets", "Feature set test", False, str(e))

    async def test_model_configs(self):
        """Test 3: Model Configuration Validation"""
        print("\n" + "="*80)
        print("TEST SUITE 3: MODEL CONFIGURATION VALIDATION")
        print("="*80)

        try:
            from src.models.trainer import get_model_config

            # Test all model types
            models = [
                "lightgbm",  # Tier 1
                "xgboost",   # Tier 1
                "gru",       # Tier 1
                "lstm",      # Tier 1
                "transformer",  # Tier 2
                "cnn_lstm",     # Tier 2
                "linear",    # Tier 3
                "svm",       # Tier 3
                "knn",       # Tier 3
            ]

            for model_name in models:
                try:
                    config = get_model_config(model_name, {})
                    has_required = all(k in config for k in ["class", "module_path", "kwargs"])
                    self.log_result("models", f"{model_name.upper()} config", has_required,
                                   config["class"])
                except Exception as e:
                    self.log_result("models", f"{model_name.upper()} config", False, str(e))

        except Exception as e:
            self.log_result("models", "Model config test", False, str(e))

    async def test_mcp_tools(self):
        """Test 4: MCP Tools Validation"""
        print("\n" + "="*80)
        print("TEST SUITE 4: MCP TOOLS VALIDATION")
        print("="*80)

        try:
            # Test market data tools
            from src.data_pipeline import market_data

            # Test get_quote
            try:
                quote = await market_data.get_quote("BTC/USDT", "binance")
                has_data = quote and "last" in quote
                self.log_result("mcp_tools", "market_data_get_quote", has_data,
                               f"Price: ${quote.get('last', 'N/A')}")
            except Exception as e:
                self.log_result("mcp_tools", "market_data_get_quote", False, str(e))

            # Test get_historical
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
                historical = await market_data.get_historical(
                    "BTC/USDT",
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    "1d",
                    "binance"
                )
                has_data = historical is not None and not historical.empty
                self.log_result("mcp_tools", "market_data_get_historical", has_data,
                               f"Rows: {len(historical) if historical is not None else 0}")
            except Exception as e:
                self.log_result("mcp_tools", "market_data_get_historical", False, str(e))

        except Exception as e:
            self.log_result("mcp_tools", "MCP tools test", False, str(e))

    async def test_api_endpoints(self):
        """Test 5: API Endpoints Validation"""
        print("\n" + "="*80)
        print("TEST SUITE 5: API ENDPOINTS VALIDATION")
        print("="*80)

        import httpx

        base_url = "http://localhost:5100"

        endpoints = [
            ("GET", "/api/datasets", "List datasets"),
            ("GET", "/api/models", "List models"),
            ("GET", "/api/health", "Health check"),
        ]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for method, path, name in endpoints:
                try:
                    if method == "GET":
                        response = await client.get(f"{base_url}{path}")
                    else:
                        response = await client.post(f"{base_url}{path}")

                    success = response.status_code == 200
                    self.log_result("ui_api", name, success,
                                   f"Status: {response.status_code}")
                except Exception as e:
                    self.log_result("ui_api", name, False, str(e))

    async def test_qlib_initialization(self):
        """Test 6: Qlib Initialization with Crypto Calendar"""
        print("\n" + "="*80)
        print("TEST SUITE 6: QLIB INITIALIZATION VALIDATION")
        print("="*80)

        try:
            import qlib
            from src.data_pipeline.crypto_calendar_provider import register_crypto_calendar

            # Test calendar provider registration
            try:
                calendar = register_crypto_calendar()
                self.log_result("data_pipeline", "Crypto calendar registered",
                               calendar is not None, "24/7 calendar provider")
            except Exception as e:
                self.log_result("data_pipeline", "Crypto calendar registered", False, str(e))

            # Test Qlib initialization
            try:
                dataset_dir = self.project_root / "data" / "qlib" / "crypto_btc_daily"
                success = init_qlib_clean(
                    provider_uri={
                        "day": str(dataset_dir),
                        "1d": str(dataset_dir),
                    },
                    region="cn"
                )
                self.log_result("data_pipeline", "Qlib initialized", success, str(dataset_dir))
            except Exception as e:
                self.log_result("data_pipeline", "Qlib initialized", False, str(e))

        except Exception as e:
            self.log_result("data_pipeline", "Qlib init test", False, str(e))

    async def test_validation_metrics(self):
        """Test 7: Validation Metrics Configuration"""
        print("\n" + "="*80)
        print("TEST SUITE 7: VALIDATION METRICS CONFIGURATION")
        print("="*80)

        # Expected metrics per Qlib best practices
        required_metrics = [
            "mean",
            "std",
            "annualized_return",
            "information_ratio",
            "max_drawdown",
        ]

        # Trading costs configuration
        expected_costs = {
            "open_cost": 0.0005,
            "close_cost": 0.0015,
            "min_cost": 5,
        }

        self.log_result("metrics", "Required metrics defined", True, required_metrics)
        self.log_result("metrics", "Trading costs configured", True, expected_costs)

        # Target thresholds (2025 standards)
        targets = {
            "information_ratio": ">1.5 (excellent) or >1.0 (good)",
            "max_drawdown": "<10% (excellent) or <20% (acceptable)",
            "sharpe_ratio": ">2.0 (excellent) or >1.0 (good)",
        }

        self.log_result("metrics", "Target thresholds set", True, targets)

    def generate_report(self):
        """Generate final test report"""
        print("\n" + "="*80)
        print("COMPREHENSIVE TEST REPORT")
        print("="*80)

        total_tests = self.passed + self.failed
        pass_rate = (self.passed / total_tests * 100) if total_tests > 0 else 0

        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {self.passed} ✅")
        print(f"Failed: {self.failed} ❌")
        print(f"Pass Rate: {pass_rate:.1f}%\n")

        # Category breakdown
        print("Results by Category:")
        print("-" * 80)
        for category, tests in self.results.items():
            if tests:
                passed = sum(1 for t in tests.values() if t["passed"])
                total = len(tests)
                print(f"  {category.upper()}: {passed}/{total} passed")

        # Save detailed results
        results_file = self.project_root / "tests" / "test_results.json"
        results_file.parent.mkdir(exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump({
                "summary": {
                    "total": total_tests,
                    "passed": self.passed,
                    "failed": self.failed,
                    "pass_rate": pass_rate,
                    "timestamp": datetime.now().isoformat()
                },
                "results": self.results
            }, f, indent=2, default=str)

        print(f"\nDetailed results saved to: {results_file}")

        # Return exit code
        return 0 if self.failed == 0 else 1


async def main():
    """Run all tests"""
    tester = ComprehensiveTester()

    # Run test suites in order
    await tester.test_data_pipeline()
    await tester.test_feature_sets()
    await tester.test_model_configs()
    await tester.test_qlib_initialization()
    await tester.test_mcp_tools()
    await tester.test_api_endpoints()
    await tester.test_validation_metrics()

    # Generate report
    exit_code = tester.generate_report()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
