"""
Integration test simulating multiple MCP tool calls to verify state bleed fix.

This test simulates the actual scenario where multiple tool calls happen
in sequence within the same Python process (as in the MCP server).
"""
import sys
from pathlib import Path
import asyncio
import pytest

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


async def test_sequential_trainer_calls():
    """
    Simulate multiple train_model calls with different datasets.
    This replicates the MCP server scenario.
    """
    from src.models.trainer import train_model
    from src.utils.qlib_state import get_qlib_config_info

    print("Testing sequential train_model calls with different datasets...\n")

    default_segments = {
        "train": ("2023-01-01", "2023-06-30"),
        "valid": ("2023-07-01", "2023-09-30"),
        "test": ("2023-10-01", "2023-12-31"),
    }

    # Simulate calling train_model with dataset 1
    print("=" * 60)
    print("CALL 1: Training with crypto_btc_daily")
    print("=" * 60)

    config_before_1 = get_qlib_config_info()
    print(f"Config before call 1: {config_before_1}\n")

    try:
        # Note: This will fail if data doesn't exist, but we're testing state management
        result1 = await train_model(
            dataset_ref="crypto_btc_daily",
            feature_set_ref="alpha158_crypto_test_new",
            handler="lightgbm",
            params={},
            segments=default_segments,
        )
        print(f"Call 1 result: {result1.get('status', 'unknown')}")
    except Exception as e:
        print(f"Call 1 error (expected if no data): {type(e).__name__}")

    config_after_1 = get_qlib_config_info()
    print(f"Config after call 1: {config_after_1}\n")

    # Simulate calling train_model with dataset 2
    print("=" * 60)
    print("CALL 2: Training with crypto_btc_full")
    print("=" * 60)

    config_before_2 = get_qlib_config_info()
    print(f"Config before call 2: {config_before_2}\n")

    try:
        result2 = await train_model(
            dataset_ref="crypto_btc_full",
            feature_set_ref="alpha158_crypto_test_new",
            handler="lightgbm",
            params={},
            segments=default_segments,
        )
        print(f"Call 2 result: {result2.get('status', 'unknown')}")
    except Exception as e:
        print(f"Call 2 error (expected if no data): {type(e).__name__}")

    config_after_2 = get_qlib_config_info()
    print(f"Config after call 2: {config_after_2}\n")

    # Verify that configs changed between calls
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    provider_1 = str(config_after_1.get('provider_uri', ''))
    provider_2 = str(config_after_2.get('provider_uri', ''))

    print(f"Provider after call 1: {provider_1}")
    print(f"Provider after call 2: {provider_2}")

    # Check that the provider_uri changed
    if 'crypto_btc_daily' in provider_1 and 'crypto_btc_full' in provider_2:
        print("\n✅ SUCCESS: Each call used the correct dataset!")
        print("   State bleed fix is working correctly.")
        return True
    elif provider_1 != provider_2:
        print("\n✅ SUCCESS: Provider URIs are different between calls")
        print(f"   Call 1: {provider_1}")
        print(f"   Call 2: {provider_2}")
        print("   State bleed fix is working correctly.")
        return True
    else:
        print("\n❌ FAILURE: Provider URIs are the same!")
        print("   State bleed may still be occurring.")
        return False


async def test_sequential_backtest_calls():
    """
    Simulate multiple backtest calls with different datasets.
    """
    from src.backtesting.engine import run_backtest
    from src.utils.qlib_state import get_qlib_config_info

    print("\n" + "=" * 60)
    print("Testing sequential backtest calls with different datasets...")
    print("=" * 60 + "\n")

    datasets = ["crypto_btc_daily", "crypto_btc_full"]
    configs = []

    for i, dataset in enumerate(datasets, 1):
        print(f"\nBacktest call {i}: {dataset}")
        print("-" * 40)

        config_before = get_qlib_config_info()
        print(f"Config before: {config_before}")

        try:
            result = await run_backtest(
                dataset_ref=dataset,
                model_id="test_model",
                costs="medium",
                rebalance="weekly",
                start_time="2024-01-01",
                end_time="2024-12-31",
                benchmark="BTC_USDT",
            )
            print(f"Result: {result.get('status', 'unknown')}")
        except Exception as e:
            print(f"Error (expected if no model): {type(e).__name__}: {str(e)[:50]}")

        config_after = get_qlib_config_info()
        configs.append(config_after)
        print(f"Config after: {config_after}")

    # Verify configs are different
    if len(configs) >= 2 and configs[0] != configs[1]:
        print("\n✅ SUCCESS: Backtest calls used different configs")
        return True
    else:
        print("\n⚠️  Warning: Could not verify different configs")
        return False


async def main():
    """Run all integration tests"""
    print("=" * 60)
    print("MCP STATE BLEED FIX - INTEGRATION TEST")
    print("=" * 60)
    print()

    results = []

    # Test 1: Sequential trainer calls
    try:
        result1 = await test_sequential_trainer_calls()
        results.append(("Trainer calls", result1))
    except Exception as e:
        print(f"\n❌ Trainer test failed with exception: {e}")
        results.append(("Trainer calls", False))

    # Test 2: Sequential backtest calls
    try:
        result2 = await test_sequential_backtest_calls()
        results.append(("Backtest calls", result2))
    except Exception as e:
        print(f"\n❌ Backtest test failed with exception: {e}")
        results.append(("Backtest calls", False))

    # Summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n🎉 All integration tests passed!")
        print("   State bleed fix is working correctly in MCP context.")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
pytestmark = pytest.mark.asyncio
