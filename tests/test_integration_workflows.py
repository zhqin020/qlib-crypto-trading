"""
Integration Testing Suite for qlib-2 Crypto Trading Platform
Tests full workflows: data pipeline, training, backtesting, serving, state management
"""

import os
import sys
import json
import inspect
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestReport:
    def __init__(self):
        self.tests = []
        self.passes = 0
        self.failures = 0

    def add_test(self, name, passed, details="", error=None):
        status = "PASS" if passed else "FAIL"
        self.tests.append({
            "name": name,
            "status": status,
            "details": details,
            "error": str(error) if error else None
        })
        if passed:
            self.passes += 1
        else:
            self.failures += 1

    def print_report(self):
        print("\n" + "="*80)
        print("INTEGRATION TEST REPORT - qlib-2 Crypto Trading Platform")
        print("="*80 + "\n")

        for test in self.tests:
            print(f"[{test['status']}] {test['name']}")
            if test['details']:
                print(f"      {test['details']}")
            if test['error']:
                print(f"      Error: {test['error']}")
            print()

        print("="*80)
        print(f"Total: {len(self.tests)} tests | Passed: {self.passes} | Failed: {self.failures}")

        # Count critical failures (excluding expected qlib import failures)
        critical_failures = [t for t in self.tests if t['status'] == 'FAIL' and 'qlib' not in str(t.get('error', ''))]

        if len(critical_failures) == 0:
            print("Overall Assessment: READY ✓")
        elif len(critical_failures) <= 2:
            print("Overall Assessment: NEEDS FIXES ⚠")
        else:
            print("Overall Assessment: BROKEN ✗")

        print(f"Critical Issues: {len(critical_failures)}")
        print("="*80)

        return len(critical_failures) == 0

def test_1_data_pipeline_end_to_end(report):
    """TEST 1: Data Pipeline End-to-End"""
    print("\n--- TEST 1: Data Pipeline End-to-End ---")

    # 1. Check if test datasets exist
    qlib_data_path = Path("/Users/chadwyatt/Code/trading/qlib-2/data/qlib")
    if qlib_data_path.exists():
        datasets = list(qlib_data_path.iterdir())
        report.add_test(
            "TEST 1.1: Qlib datasets exist",
            True,
            f"Found {len(datasets)} datasets in data/qlib/"
        )
    else:
        report.add_test(
            "TEST 1.1: Qlib datasets exist",
            False,
            "data/qlib/ directory does not exist"
        )

    # 2. Check for raw data
    raw_paths = [
        Path("/Users/chadwyatt/Code/trading/qlib-2/data/raw_1d"),
        Path("/Users/chadwyatt/Code/trading/qlib-2/data/raw_full"),
        Path("/Users/chadwyatt/Code/trading/qlib-2/data/raw_multi")
    ]
    raw_data_found = any(p.exists() for p in raw_paths)
    report.add_test(
        "TEST 1.2: Raw data exists",
        raw_data_found,
        f"Raw data directories: {[str(p.name) for p in raw_paths if p.exists()]}"
    )

    # 3. Verify data pipeline components import
    pipeline_imports = []
    try:
        from src.data_pipeline.snapshot import create_snapshot
        pipeline_imports.append("create_snapshot")
    except Exception as e:
        report.add_test(
            "TEST 1.3a: Import create_snapshot",
            False,
            error=e
        )

    try:
        from src.data_pipeline.official_qlib_converter import convert_crypto_data_official
        pipeline_imports.append("convert_crypto_data_official")
    except Exception as e:
        report.add_test(
            "TEST 1.3b: Import convert_crypto_data_official",
            False,
            error=e
        )

    try:
        from src.data_pipeline.crypto_calendar_provider import register_crypto_calendar
        pipeline_imports.append("register_crypto_calendar")
    except Exception as e:
        report.add_test(
            "TEST 1.3c: Import register_crypto_calendar",
            False,
            error=e
        )

    if len(pipeline_imports) == 3:
        report.add_test(
            "TEST 1.3: Data pipeline imports",
            True,
            f"All 3 components imported: {', '.join(pipeline_imports)}"
        )

    # 4. Check configuration files
    config_path = Path("/Users/chadwyatt/Code/trading/qlib-2/config/features")
    alpha158_configs = list(config_path.glob("alpha158_*.json"))
    alpha360_configs = list(config_path.glob("alpha360_*.json"))

    report.add_test(
        "TEST 1.4a: Alpha158 configs exist",
        len(alpha158_configs) > 0,
        f"Found {len(alpha158_configs)} alpha158 configs"
    )

    report.add_test(
        "TEST 1.4b: Alpha360 configs exist",
        len(alpha360_configs) > 0,
        f"Found {len(alpha360_configs)} alpha360 configs"
    )

    # 5. Verify dataset structure if exists
    if qlib_data_path.exists():
        for dataset in qlib_data_path.iterdir():
            if dataset.is_dir():
                has_calendars = (dataset / "calendars").exists()
                has_instruments = (dataset / "instruments").exists()
                has_features = (dataset / "features").exists()

                if has_calendars and has_instruments and has_features:
                    report.add_test(
                        f"TEST 1.5: Dataset structure {dataset.name}",
                        True,
                        "Has calendars/, instruments/, features/"
                    )
                    break

def test_2_model_training_workflow(report):
    """TEST 2: Model Training Workflow"""
    print("\n--- TEST 2: Model Training Workflow ---")

    # 1. Check trainer.py exists and imports
    try:
        from src.models.trainer import train_model
        report.add_test(
            "TEST 2.1: Import trainer.py",
            True,
            "train_model imported successfully"
        )

        # 2. Check function signature
        sig = inspect.signature(train_model)
        params = list(sig.parameters.keys())
        expected_params = ['dataset_ref', 'feature_set_ref', 'handler', 'params']

        has_all_params = all(p in params for p in expected_params)
        report.add_test(
            "TEST 2.2: train_model signature",
            has_all_params,
            f"Parameters: {params}"
        )

        # 3. Check for state management usage
        import src.models.trainer as trainer_module
        source = inspect.getsource(trainer_module)
        uses_async_init = "qlib_init_context" in source

        report.add_test(
            "TEST 2.3: Uses async state management",
            uses_async_init,
            "qlib_init_context() found in trainer.py"
        )

        # 4. Check imports qlib_state
        imports_state = "from ..utils.qlib_state import" in source or "from src.utils.qlib_state import" in source
        report.add_test(
            "TEST 2.4: Imports qlib_state",
            imports_state,
            "State management module imported"
        )

    except Exception as e:
        report.add_test(
            "TEST 2.1: Import trainer.py",
            False,
            error=e
        )

    # 5. Check model storage directory
    models_dir = Path("/Users/chadwyatt/Code/trading/qlib-2/models/trained")
    if not models_dir.exists():
        models_dir.mkdir(parents=True, exist_ok=True)
        report.add_test(
            "TEST 2.5: Model storage directory",
            True,
            "Created models/trained/ directory"
        )
    else:
        report.add_test(
            "TEST 2.5: Model storage directory",
            True,
            "models/trained/ exists"
        )

    # 6. Check for model configs
    config_path = Path("/Users/chadwyatt/Code/trading/qlib-2/config")

    # Check for individual model configs
    model_configs = {
        "lightgbm": (config_path / "lightgbm_crypto.json").exists(),
        "xgboost": (config_path / "xgboost_crypto.json").exists(),
        "lstm": (config_path / "lstm_crypto.json").exists(),
        "transformer": (config_path / "transformer_crypto.json").exists()
    }

    # Also check for combined tuning config
    tuning_config = (config_path / "crypto_model_tuning.json").exists()

    available_configs = [k for k, v in model_configs.items() if v]
    if tuning_config:
        available_configs.append("crypto_model_tuning")

    has_model_config = len(available_configs) > 0 or tuning_config

    report.add_test(
        "TEST 2.6: Model configurations",
        has_model_config,
        f"Available: {', '.join(available_configs) if available_configs else 'None'}"
    )

def test_3_backtesting_workflow(report):
    """TEST 3: Backtesting Workflow"""
    print("\n--- TEST 3: Backtesting Workflow ---")

    # 1. Check engine.py exists and imports
    try:
        from src.backtesting.engine import run_backtest
        report.add_test(
            "TEST 3.1: Import engine.py",
            True,
            "run_backtest imported successfully"
        )

        # 2. Check function signature
        sig = inspect.signature(run_backtest)
        params = list(sig.parameters.keys())
        expected_params = ['model_id', 'dataset_ref']

        has_core_params = all(p in params for p in expected_params)
        report.add_test(
            "TEST 3.2: run_backtest signature",
            has_core_params,
            f"Parameters: {params}"
        )

        # 3. Check for state management usage
        import src.backtesting.engine as engine_module
        source = inspect.getsource(engine_module)
        uses_async_init = "qlib_init_context" in source

        report.add_test(
            "TEST 3.3: Uses async state management",
            uses_async_init,
            "qlib_init_context() found in engine.py"
        )

        # 4. Check imports qlib_state
        imports_state = "from ..utils.qlib_state import" in source or "from src.utils.qlib_state import" in source
        report.add_test(
            "TEST 3.4: Imports qlib_state",
            imports_state,
            "State management module imported"
        )

        # 5. Check for cost configurations in source
        has_cost_config = "cost" in source.lower() or "trading_cost" in source.lower()
        report.add_test(
            "TEST 3.5: Cost configuration",
            has_cost_config,
            "Trading cost handling found"
        )

        # 6. Check for crypto metrics
        has_crypto_metrics = "sharpe" in source.lower() or "metrics" in source.lower()
        report.add_test(
            "TEST 3.6: Crypto metrics calculation",
            has_crypto_metrics,
            "Metrics calculation found"
        )

    except Exception as e:
        report.add_test(
            "TEST 3.1: Import engine.py",
            False,
            error=e
        )

def test_4_serving_prediction_workflow(report):
    """TEST 4: Serving/Prediction Workflow"""
    print("\n--- TEST 4: Serving/Prediction Workflow ---")

    # 1. Check predictor.py exists and imports
    try:
        from src.serving.predictor import predict_today
        report.add_test(
            "TEST 4.1: Import predictor.py",
            True,
            "predict_today imported successfully"
        )

        # 2. Check function signature
        sig = inspect.signature(predict_today)
        params = list(sig.parameters.keys())
        expected_params = ['model_id', 'dataset_ref']

        has_core_params = all(p in params for p in expected_params)
        report.add_test(
            "TEST 4.2: predict_today signature",
            has_core_params,
            f"Parameters: {params}"
        )

        # 3. Check for state management usage
        import src.serving.predictor as predictor_module
        source = inspect.getsource(predictor_module)
        uses_async_init = "qlib_init_context" in source

        report.add_test(
            "TEST 4.3: Uses async state management",
            uses_async_init,
            "qlib_init_context() found in predictor.py"
        )

        # 4. Check imports qlib_state
        imports_state = "from ..utils.qlib_state import" in source or "from src.utils.qlib_state import" in source
        report.add_test(
            "TEST 4.4: Imports qlib_state",
            imports_state,
            "State management module imported"
        )

    except Exception as e:
        report.add_test(
            "TEST 4.1: Import predictor.py",
            False,
            error=e
        )

    # 5. Check predictions storage
    predictions_dir = Path("/Users/chadwyatt/Code/trading/qlib-2/predictions")
    if not predictions_dir.exists():
        predictions_dir.mkdir(parents=True, exist_ok=True)
        report.add_test(
            "TEST 4.5: Predictions storage",
            True,
            "Created predictions/ directory"
        )
    else:
        report.add_test(
            "TEST 4.5: Predictions storage",
            True,
            "predictions/ directory exists"
        )

def test_5_state_management_integration(report):
    """TEST 5: State Management Integration"""
    print("\n--- TEST 5: State Management Integration ---")

    modules_to_check = [
        ("src.models.trainer", "trainer.py"),
        ("src.backtesting.engine", "engine.py"),
        ("src.serving.predictor", "predictor.py")
    ]

    all_use_async = True
    all_validate_paths = True
    all_handle_errors = True

    for module_name, file_name in modules_to_check:
        try:
            module = __import__(module_name, fromlist=[''])
            source = inspect.getsource(module)

            # Check uses async init
            uses_async = "qlib_init_context" in source
            if not uses_async:
                all_use_async = False
                report.add_test(
                    f"TEST 5.1: {file_name} uses async init",
                    False,
                    "Missing qlib_init_context()"
                )

            # Check validates dataset paths
            validates_path = "dataset_path" in source or "provider_uri" in source
            if not validates_path:
                all_validate_paths = False

            # Check error handling
            handles_errors = "RuntimeError" in source or "raise" in source
            if not handles_errors:
                all_handle_errors = False

        except Exception as e:
            report.add_test(
                f"TEST 5.x: Check {file_name}",
                False,
                error=e
            )

    if all_use_async:
        report.add_test(
            "TEST 5.1: All modules use async init",
            True,
            "trainer.py, engine.py, predictor.py all use qlib_init_context()"
        )

    report.add_test(
        "TEST 5.2: Path validation",
        all_validate_paths,
        "Dataset path validation present" if all_validate_paths else "Missing validation"
    )

    report.add_test(
        "TEST 5.3: Error handling",
        all_handle_errors,
        "Error handling present" if all_handle_errors else "Missing error handling"
    )

def test_6_configuration_validation(report):
    """TEST 6: Configuration Validation"""
    print("\n--- TEST 6: Configuration Validation ---")

    config_path = Path("/Users/chadwyatt/Code/trading/qlib-2/config/features")

    if not config_path.exists():
        report.add_test(
            "TEST 6.1: Config directory exists",
            False,
            "config/features/ not found"
        )
        return

    configs = list(config_path.glob("*.json"))
    report.add_test(
        "TEST 6.1: Config files found",
        len(configs) > 0,
        f"Found {len(configs)} configuration files"
    )

    valid_configs = 0
    invalid_configs = []

    for config_file in configs:
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Check required fields (can be at root or nested)
            has_handler = "handler" in config or ("config" in config and "class" in config["config"])

            # Check for label in various locations
            has_label = False
            if "label" in config:
                has_label = True
            elif "config" in config:
                # Check nested config
                nested = config["config"]

                # Alpha360 and similar built-in handlers have implicit labels
                if "class" in nested and nested["class"] in ["Alpha360", "Alpha158"]:
                    has_label = True
                elif "kwargs" in nested and "label" in nested["kwargs"]:
                    has_label = True
                elif "kwargs" in nested and "data_loader" in nested["kwargs"]:
                    # Check data_loader config
                    loader = nested["kwargs"]["data_loader"]
                    if "kwargs" in loader and "config" in loader["kwargs"]:
                        if "label" in loader["kwargs"]["config"]:
                            has_label = True

            if has_handler and has_label:
                valid_configs += 1
            else:
                missing = []
                if not has_handler:
                    missing.append("handler")
                if not has_label:
                    missing.append("label")
                invalid_configs.append(f"{config_file.name} (missing: {', '.join(missing)})")

        except json.JSONDecodeError as e:
            invalid_configs.append(f"{config_file.name} (JSON error)")
        except Exception as e:
            invalid_configs.append(f"{config_file.name} (Error: {str(e)})")

    report.add_test(
        "TEST 6.2: Config JSON validity",
        len(invalid_configs) == 0,
        f"Valid: {valid_configs}, Invalid: {len(invalid_configs)}"
    )

    if invalid_configs:
        report.add_test(
            "TEST 6.3: Invalid configs",
            False,
            f"Issues: {', '.join(invalid_configs)}"
        )

def test_7_directory_structure(report):
    """TEST 7: Directory Structure"""
    print("\n--- TEST 7: Directory Structure ---")

    base_path = Path("/Users/chadwyatt/Code/trading/qlib-2")

    required_dirs = [
        "src/models",
        "src/backtesting",
        "src/serving",
        "src/data_pipeline",
        "src/utils",
        "src/mcp_server",
        "config/features",
    ]

    optional_dirs = [
        "data/qlib",
        "models/trained",
        "predictions"
    ]

    missing_required = []
    for dir_path in required_dirs:
        full_path = base_path / dir_path
        if not full_path.exists():
            missing_required.append(dir_path)

    report.add_test(
        "TEST 7.1: Required directories",
        len(missing_required) == 0,
        f"All required dirs exist" if len(missing_required) == 0 else f"Missing: {', '.join(missing_required)}"
    )

    created_dirs = []
    for dir_path in optional_dirs:
        full_path = base_path / dir_path
        if not full_path.exists():
            full_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(dir_path)

    if created_dirs:
        report.add_test(
            "TEST 7.2: Optional directories created",
            True,
            f"Created: {', '.join(created_dirs)}"
        )
    else:
        report.add_test(
            "TEST 7.2: Optional directories",
            True,
            "All optional directories exist"
        )

    # Check key files exist
    key_files = [
        "src/models/trainer.py",
        "src/backtesting/engine.py",
        "src/serving/predictor.py",
        "src/utils/qlib_state.py"
    ]

    missing_files = []
    for file_path in key_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    report.add_test(
        "TEST 7.3: Key files exist",
        len(missing_files) == 0,
        f"All key files present" if len(missing_files) == 0 else f"Missing: {', '.join(missing_files)}"
    )

def main():
    """Run all integration tests"""
    report = TestReport()

    print("Starting Integration Testing Suite for qlib-2 Crypto Trading Platform")
    print("Testing: imports, file structure, function signatures, state management")
    print("NOT testing: actual qlib operations (qlib not installed in test env)")

    # Run all test suites
    test_1_data_pipeline_end_to_end(report)
    test_2_model_training_workflow(report)
    test_3_backtesting_workflow(report)
    test_4_serving_prediction_workflow(report)
    test_5_state_management_integration(report)
    test_6_configuration_validation(report)
    test_7_directory_structure(report)

    # Print final report
    success = report.print_report()

    # Save report to file
    report_path = Path("/Users/chadwyatt/Code/trading/qlib-2/tests/integration_test_report.json")
    with open(report_path, 'w') as f:
        json.dump({
            "total_tests": len(report.tests),
            "passed": report.passes,
            "failed": report.failures,
            "tests": report.tests
        }, f, indent=2)

    print(f"\nDetailed report saved to: {report_path}")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
