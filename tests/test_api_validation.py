#!/usr/bin/env python3
"""
Test script to verify API input validation
"""
import requests
import json

BASE_URL = "http://localhost:5100/api"

def test_train_model_validation():
    """Test TrainModelRequest validation"""
    print("\n=== Testing Train Model Validation ===")

    # Test 1: Path traversal in dataset
    print("\n1. Testing path traversal protection...")
    response = requests.post(f"{BASE_URL}/models/train", json={
        "dataset": "../../../etc/passwd",
        "feature_handler": "alpha158",
        "model_handler": "lightgbm"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject path traversal"

    # Test 2: Invalid feature handler
    print("\n2. Testing invalid feature handler...")
    response = requests.post(f"{BASE_URL}/models/train", json={
        "dataset": "crypto_btc",
        "feature_handler": "invalid_handler",
        "model_handler": "lightgbm"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject invalid feature handler"

    # Test 3: Invalid model handler
    print("\n3. Testing invalid model handler...")
    response = requests.post(f"{BASE_URL}/models/train", json={
        "dataset": "crypto_btc",
        "feature_handler": "alpha158",
        "model_handler": "malicious_model"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject invalid model handler"

    # Test 4: Params too large
    print("\n4. Testing params size limit...")
    large_params = {"data": "x" * 15000}
    response = requests.post(f"{BASE_URL}/models/train", json={
        "dataset": "crypto_btc",
        "feature_handler": "alpha158",
        "model_handler": "lightgbm",
        "params": large_params
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject large params"

    print("\n✓ All train model validation tests passed!")


def test_backtest_validation():
    """Test BacktestRequest validation"""
    print("\n=== Testing Backtest Validation ===")

    # Test 1: Path traversal in model_id
    print("\n1. Testing path traversal in model_id...")
    response = requests.post(f"{BASE_URL}/backtests/run", json={
        "model_id": "../../../etc/passwd",
        "dataset": "crypto_btc",
        "costs": "medium"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject path traversal"

    # Test 2: Invalid costs
    print("\n2. Testing invalid costs...")
    response = requests.post(f"{BASE_URL}/backtests/run", json={
        "model_id": "model123",
        "dataset": "crypto_btc",
        "costs": "ultra_high"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject invalid costs"

    # Test 3: Invalid rebalance frequency
    print("\n3. Testing invalid rebalance frequency...")
    response = requests.post(f"{BASE_URL}/backtests/run", json={
        "model_id": "model123",
        "dataset": "crypto_btc",
        "costs": "medium",
        "rebalance": "hourly"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject invalid rebalance"

    print("\n✓ All backtest validation tests passed!")


def test_prediction_validation():
    """Test PredictionRequest validation"""
    print("\n=== Testing Prediction Validation ===")

    # Test 1: Invalid date format
    print("\n1. Testing invalid date format...")
    response = requests.post(f"{BASE_URL}/predictions/generate", json={
        "model_id": "model123",
        "dataset": "crypto_btc",
        "prediction_date": "2025/10/07"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject invalid date format"

    # Test 2: Future date too far
    print("\n2. Testing date too far in future...")
    response = requests.post(f"{BASE_URL}/predictions/generate", json={
        "model_id": "model123",
        "dataset": "crypto_btc",
        "prediction_date": "2030-01-01"
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 422, "Should reject date too far in future"

    print("\n✓ All prediction validation tests passed!")


def test_process_validation():
    """Test process endpoint validation"""
    print("\n=== Testing Process Endpoint Validation ===")

    # Test 1: Invalid process_id format
    print("\n1. Testing invalid process_id format...")
    response = requests.get(f"{BASE_URL}/processes/../../etc/passwd")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400, "Should reject invalid process_id"

    # Test 2: Invalid limit parameter
    print("\n2. Testing invalid limit parameter...")
    response = requests.get(f"{BASE_URL}/processes/test_process/logs?limit=-1")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400, "Should reject negative limit"

    # Test 3: Limit clamping
    print("\n3. Testing limit clamping (should succeed with limit=1000)...")
    response = requests.get(f"{BASE_URL}/processes/test_process/logs?limit=5000")
    print(f"   Status: {response.status_code}")
    # This might be 404 if process doesn't exist, which is fine
    if response.status_code == 404:
        print(f"   Response: {response.json()}")
        print("   (404 is expected if process doesn't exist)")

    print("\n✓ All process validation tests passed!")


def test_model_endpoint_validation():
    """Test model endpoint validation"""
    print("\n=== Testing Model Endpoint Validation ===")

    # Test 1: Path traversal in model_id
    print("\n1. Testing path traversal in model_id...")
    response = requests.get(f"{BASE_URL}/models/../../../etc/passwd")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400, "Should reject path traversal"

    print("\n✓ All model endpoint validation tests passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("API Input Validation Test Suite")
    print("=" * 60)
    print("\nNOTE: This assumes the API server is running on localhost:5100")
    print("Start the server with: python -m uvicorn src.ui.api_enhanced:app --port 5100")
    print("\nPress Enter to continue or Ctrl+C to abort...")
    input()

    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL.replace('/api', '')}/api/health")
        if response.status_code != 200:
            print("\n❌ Server is not responding correctly")
            exit(1)
        print(f"✓ Server is running (version: {response.json().get('version')})")

        # Run all tests
        test_train_model_validation()
        test_backtest_validation()
        test_prediction_validation()
        test_process_validation()
        test_model_endpoint_validation()

        print("\n" + "=" * 60)
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server on localhost:5100")
        print("Please start the server first:")
        print("  python -m uvicorn src.ui.api_enhanced:app --port 5100")
        exit(1)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
