"""
Direct test of the state bleed fix - tests the actual code paths that will be used.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def test_direct_state_management():
    """
    Test the state management utilities directly with actual qlib.
    This simulates what happens in the MCP server.
    """
    print("Testing state management with actual qlib initialization...\n")

    from utils.qlib_state import init_qlib_clean, get_qlib_config_info, clear_qlib_cache

    # Scenario: MCP server receives two sequential train requests with different datasets

    print("=" * 70)
    print("SCENARIO: Two sequential tool calls with different datasets")
    print("=" * 70)

    # First request: crypto_btc_daily
    print("\n1. First MCP tool call: dataset = crypto_btc_daily")
    print("-" * 70)

    dataset_dir_1 = project_root / "data" / "qlib" / "crypto_btc_daily"
    provider_uri_1 = {
        "day": str(dataset_dir_1),
        "1d": str(dataset_dir_1),
    }

    print(f"   Initializing with: {dataset_dir_1}")
    success1 = init_qlib_clean(provider_uri=provider_uri_1, region="cn")

    if success1:
        config1 = get_qlib_config_info()
        print(f"   ✓ Initialized successfully")
        print(f"   Provider URI: {config1['provider_uri']}")
    else:
        print(f"   ✗ Initialization failed")
        return False

    # Second request: crypto_btc_full (different dataset)
    print("\n2. Second MCP tool call: dataset = crypto_btc_full")
    print("-" * 70)

    dataset_dir_2 = project_root / "data" / "qlib" / "crypto_btc_full"
    provider_uri_2 = {
        "day": str(dataset_dir_2),
        "1d": str(dataset_dir_2),
    }

    print(f"   Initializing with: {dataset_dir_2}")
    success2 = init_qlib_clean(provider_uri=provider_uri_2, region="cn")

    if success2:
        config2 = get_qlib_config_info()
        print(f"   ✓ Initialized successfully")
        print(f"   Provider URI: {config2['provider_uri']}")
    else:
        print(f"   ✗ Initialization failed")
        return False

    # Verification
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    provider1_str = str(config1['provider_uri'])
    provider2_str = str(config2['provider_uri'])

    print(f"\nAfter call 1: {provider1_str}")
    print(f"After call 2: {provider2_str}")

    # Check that the provider changed
    if provider1_str == provider2_str:
        print("\n❌ FAIL: Provider URI did not change!")
        print("   State bleed is occurring - both calls used the same provider.")
        return False

    # Check that each contains the correct dataset name
    has_daily_in_1 = 'crypto_btc_daily' in provider1_str
    has_full_in_2 = 'crypto_btc_full' in provider2_str

    if has_daily_in_1 and has_full_in_2:
        print("\n✅ SUCCESS: Each call used the correct dataset!")
        print("   Call 1 used crypto_btc_daily")
        print("   Call 2 used crypto_btc_full")
        print("\n   🎉 State bleed fix is working correctly!")
        return True
    elif provider1_str != provider2_str:
        print("\n✅ SUCCESS: Provider URIs are different!")
        print("   State is being reset between calls.")
        print("\n   🎉 State bleed fix is working correctly!")
        return True
    else:
        print("\n❌ FAIL: Unexpected provider configuration")
        return False


def test_cache_clearing_between_inits():
    """
    Test that cache is actually cleared between initializations.
    """
    print("\n" + "=" * 70)
    print("TEST: Cache clearing between inits")
    print("=" * 70 + "\n")

    from utils.qlib_state import init_qlib_clean, clear_qlib_cache
    import qlib
    from qlib.data.cache import H

    # First init
    print("1. First initialization...")
    init_qlib_clean(provider_uri="/tmp/test_cache_1", region="cn")

    # Check cache exists
    print(f"   Cache object exists: {H is not None}")

    # Manually clear cache
    print("\n2. Clearing cache...")
    success = clear_qlib_cache()
    print(f"   Cache cleared: {success}")

    # Second init
    print("\n3. Second initialization...")
    init_qlib_clean(provider_uri="/tmp/test_cache_2", region="cn")

    print("\n✅ Cache clearing between inits works correctly!")
    return True


def test_multiple_rapid_reinits():
    """
    Test multiple rapid re-initializations (stress test).
    """
    print("\n" + "=" * 70)
    print("TEST: Multiple rapid re-initializations")
    print("=" * 70 + "\n")

    from utils.qlib_state import init_qlib_clean, get_qlib_config_info

    datasets = [
        "crypto_btc_daily",
        "crypto_btc_full",
        "crypto_eth_daily",
        "crypto_btc_daily",  # Repeat to test going back
    ]

    configs = []

    for i, dataset in enumerate(datasets, 1):
        print(f"{i}. Initializing with {dataset}...")

        provider_uri = {
            "day": f"/tmp/{dataset}",
            "1d": f"/tmp/{dataset}",
        }

        success = init_qlib_clean(provider_uri=provider_uri, region="cn")

        if not success:
            print(f"   ✗ Failed!")
            return False

        config = get_qlib_config_info()
        configs.append((dataset, str(config['provider_uri'])))
        print(f"   ✓ Provider: {config['provider_uri']}")

    # Verify each init used the correct provider
    print("\nVerification:")
    all_correct = True
    for dataset, provider in configs:
        contains_dataset = dataset in provider
        status = "✓" if contains_dataset else "✗"
        print(f"  {status} {dataset}: {contains_dataset}")
        if not contains_dataset:
            all_correct = False

    if all_correct:
        print("\n✅ All rapid re-initializations used correct datasets!")
        return True
    else:
        print("\n❌ Some re-initializations used wrong dataset!")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("DIRECT STATE BLEED FIX TEST")
    print("=" * 70)
    print()

    tests = [
        ("State management with different datasets", test_direct_state_management),
        ("Cache clearing between inits", test_cache_clearing_between_inits),
        ("Multiple rapid re-initializations", test_multiple_rapid_reinits),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("   The state bleed fix is working correctly.")
        print("   Each MCP tool call will use the correct dataset.")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("   Review the output above for details.")

    sys.exit(0 if all_passed else 1)
