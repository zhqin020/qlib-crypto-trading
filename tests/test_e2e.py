#!/usr/bin/env python3
"""
End-to-End Testing Script
Tests all platform components without needing API keys
"""

import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_imports():
    """Test that all modules can be imported"""
    print_section("TEST 1: Module Imports")

    try:
        print("✓ Importing FastAPI components...")
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        print("✓ Importing UI components...")
        from ui.events import EventBroadcaster

        print("✓ All imports successful!")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_event_broadcaster():
    """Test event broadcasting system"""
    print_section("TEST 2: Event Broadcasting System")

    try:
        from ui.events import EventBroadcaster

        broadcaster = EventBroadcaster()
        print(f"✓ EventBroadcaster created")
        print(f"  - Active connections: {len(broadcaster.active_connections)}")
        print(f"  - Event history: {len(broadcaster.event_history)}")

        # Test adding event to history
        import asyncio
        asyncio.run(broadcaster.broadcast("test", {"message": "Test event"}))

        print(f"✓ Event broadcast test passed")
        print(f"  - Event history after broadcast: {len(broadcaster.event_history)}")

        return True
    except Exception as e:
        print(f"✗ Event broadcaster test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_structure():
    """Test API structure without starting server"""
    print_section("TEST 3: API Structure")

    try:
        from ui import api_enhanced

        print(f"✓ API module loaded")
        print(f"  - FastAPI app: {api_enhanced.app.title}")
        print(f"  - Version: {api_enhanced.app.version}")

        # Count routes
        routes = [route for route in api_enhanced.app.routes]
        print(f"  - Total routes: {len(routes)}")

        # List main endpoints
        api_routes = [r for r in routes if hasattr(r, 'path') and r.path.startswith('/api/')]
        print(f"  - API endpoints: {len(api_routes)}")

        for route in api_routes[:5]:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ', '.join(route.methods) if route.methods else 'N/A'
                print(f"    • {methods:10} {route.path}")

        print("✓ API structure validated")
        return True
    except Exception as e:
        print(f"✗ API structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_directory_structure():
    """Test that all required directories exist"""
    print_section("TEST 4: Directory Structure")

    project_root = Path(__file__).parent.parent

    required_dirs = [
        "src/ui",
        "src/mcp_server",
        "src/data_pipeline",
        "src/models",
        "src/backtesting",
        "src/serving",
        "data",
        "models/trained",
        "config",
        "scripts",
    ]

    all_exist = True
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"{status} {dir_path}")
        if not exists:
            all_exist = False

    if all_exist:
        print("\n✓ All required directories exist")
    else:
        print("\n✗ Some directories missing")

    return all_exist

def test_configuration_files():
    """Test that configuration files are valid"""
    print_section("TEST 5: Configuration Files")

    project_root = Path(__file__).parent.parent

    files_to_check = {
        "requirements.txt": "Dependencies",
        "docker-compose.yml": "Docker config",
        ".env.example": "Environment template",
        "Makefile": "Make commands",
        "README.md": "Documentation",
    }

    all_valid = True
    for filename, description in files_to_check.items():
        filepath = project_root / filename
        exists = filepath.exists()
        status = "✓" if exists else "✗"
        size = filepath.stat().st_size if exists else 0
        print(f"{status} {filename:25} ({description:20}) - {size:,} bytes")
        if not exists:
            all_valid = False

    if all_valid:
        print("\n✓ All configuration files present")
    else:
        print("\n✗ Some configuration files missing")

    return all_valid

def test_mock_data_operations():
    """Test data operations with mock data (no API keys needed)"""
    print_section("TEST 6: Mock Data Operations")

    try:
        from ui.events import get_event_broadcaster
        import asyncio

        broadcaster = get_event_broadcaster()

        # Simulate data update event
        print("• Testing data update event...")
        asyncio.run(broadcaster.broadcast_data_update("test_download", {
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "count": 2
        }))
        print("  ✓ Data update event broadcasted")

        # Simulate model update event
        print("• Testing model update event...")
        asyncio.run(broadcaster.broadcast_model_update(
            "test_model_123",
            "completed",
            {"accuracy": 0.85, "loss": 0.15}
        ))
        print("  ✓ Model update event broadcasted")

        # Simulate notification
        print("• Testing notification event...")
        asyncio.run(broadcaster.broadcast_notification(
            "success",
            "Test completed successfully",
            {"test_id": "e2e_001"}
        ))
        print("  ✓ Notification event broadcasted")

        # Check event history
        print(f"\n✓ Event history contains {len(broadcaster.event_history)} events")

        return True
    except Exception as e:
        print(f"✗ Mock data operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_port_configuration():
    """Test that ports are correctly configured"""
    print_section("TEST 7: Port Configuration")

    project_root = Path(__file__).parent.parent

    # Check .env.example
    env_file = project_root / ".env.example"
    if env_file.exists():
        content = env_file.read_text()

        checks = {
            "API_PORT=5100": "API port",
            ":5110": "PostgreSQL port",
            ":5120": "Redis port",
        }

        all_correct = True
        for check, description in checks.items():
            if check in content:
                print(f"✓ {description} configured correctly ({check})")
            else:
                print(f"✗ {description} NOT configured correctly (looking for {check})")
                all_correct = False

        if all_correct:
            print("\n✓ All ports configured correctly")
            return True
        else:
            print("\n✗ Some ports incorrectly configured")
            return False
    else:
        print("✗ .env.example not found")
        return False

def generate_report(results):
    """Generate test report"""
    print_section("TEST REPORT")

    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed

    print(f"Total Tests:  {total}")
    print(f"Passed:       {passed} ✓")
    print(f"Failed:       {failed} ✗")
    print(f"Success Rate: {(passed/total*100):.1f}%")

    print("\nDetailed Results:")
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} - {test_name}")

    return passed == total

def main():
    """Run all tests"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║        Qlib Crypto Trading Platform - E2E Test Suite           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    results = {}

    # Run all tests
    results["Module Imports"] = test_imports()
    results["Event Broadcasting"] = test_event_broadcaster()
    results["API Structure"] = test_api_structure()
    results["Directory Structure"] = test_directory_structure()
    results["Configuration Files"] = test_configuration_files()
    results["Mock Data Operations"] = test_mock_data_operations()
    results["Port Configuration"] = test_port_configuration()

    # Generate report
    all_passed = generate_report(results)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Platform is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the results above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
