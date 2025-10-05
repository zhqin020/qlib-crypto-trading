#!/usr/bin/env python3
"""
Validate platform setup and configuration
"""

import sys
from pathlib import Path
import importlib.util

def check_color(passed):
    """Return colored checkmark or X"""
    return "✓" if passed else "✗"

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 8
    print(f"{check_color(passed)} Python version: {version.major}.{version.minor}.{version.micro}")
    return passed

def check_dependencies():
    """Check required Python packages"""
    required = [
        "pandas",
        "numpy",
        "qlib",
        "ccxt",
        "fastapi",
        "uvicorn",
        "torch",
        "lightgbm",
        "sklearn",
    ]

    all_passed = True
    for package in required:
        try:
            # Try to import
            if package == "sklearn":
                importlib.import_module("sklearn")
            else:
                importlib.import_module(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - NOT INSTALLED")
            all_passed = False

    return all_passed

def check_directory_structure():
    """Check directory structure"""
    required_dirs = [
        "src/mcp_server",
        "src/data_pipeline",
        "src/models",
        "src/backtesting",
        "src/serving",
        "src/ui",
        "data/raw",
        "data/qlib",
        "models/trained",
        "backtests",
        "predictions",
        "experiments",
        "config",
        "scripts",
        "tests",
    ]

    all_passed = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        exists = path.exists() and path.is_dir()
        if not exists:
            all_passed = False
        print(f"{check_color(exists)} {dir_path}")

    return all_passed

def check_scripts():
    """Check that scripts exist and are executable"""
    scripts = [
        "scripts/download_sample_data.py",
        "scripts/convert_to_qlib.py",
        "scripts/train_sample_model.py",
        "scripts/run_backtest.py",
        "scripts/predict.py",
        "scripts/start_server.sh",
        "scripts/start_mcp_server.sh",
    ]

    all_passed = True
    for script_path in scripts:
        path = Path(script_path)
        exists = path.exists()
        if not exists:
            all_passed = False
        print(f"{check_color(exists)} {script_path}")

    return all_passed

def check_config_files():
    """Check configuration files"""
    configs = [
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        "README.md",
        "QUICKSTART.md",
        "Makefile",
    ]

    all_passed = True
    for config in configs:
        path = Path(config)
        exists = path.exists()
        if not exists:
            all_passed = False
        print(f"{check_color(exists)} {config}")

    return all_passed

def main():
    """Run all validation checks"""
    print("=" * 60)
    print("Qlib Crypto Trading Platform - Setup Validation")
    print("=" * 60)
    print()

    results = {}

    # Python version
    print("1. Python Version Check:")
    results["python"] = check_python_version()
    print()

    # Dependencies
    print("2. Python Dependencies:")
    results["dependencies"] = check_dependencies()
    print()

    # Directory structure
    print("3. Directory Structure:")
    results["directories"] = check_directory_structure()
    print()

    # Scripts
    print("4. Scripts:")
    results["scripts"] = check_scripts()
    print()

    # Config files
    print("5. Configuration Files:")
    results["configs"] = check_config_files()
    print()

    # Summary
    print("=" * 60)
    print("Validation Summary:")
    print("=" * 60)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"{check_color(passed)} {check.title()}: {status}")

    print()

    if all_passed:
        print("✓ All checks passed! Platform is ready to use.")
        print()
        print("Next steps:")
        print("  1. Download sample data: make download-data")
        print("  2. Convert to Qlib format: make convert")
        print("  3. Train a model: make train")
        print("  4. Start API server: make api")
        print()
        print("See QUICKSTART.md for detailed instructions.")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print()
        print("To install missing dependencies:")
        print("  pip install -r requirements.txt")
        print()
        print("To create missing directories:")
        print("  make setup")
        return 1

if __name__ == "__main__":
    sys.exit(main())
