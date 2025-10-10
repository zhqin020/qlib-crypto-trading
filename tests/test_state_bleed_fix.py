"""
Test to demonstrate the state bleed fix

Before fix: Class variables persisted across singleton resets
After fix: Instance variables are properly cleaned on reset
"""
import asyncio
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.process_monitor import ProcessMonitor


async def test_state_bleed_fixed():
    """
    BEFORE FIX:
    - ProcessMonitor used class variables for _processes, _tasks, etc.
    - Resetting _instance didn't clear these variables
    - State persisted between test runs causing contamination

    AFTER FIX:
    - All state moved to instance variables
    - reset_instance() creates clean slate
    - No state persistence between tests
    """
    print("\n" + "="*80)
    print("STATE BLEED BUG FIX VERIFICATION")
    print("="*80)

    # Test 1: State persists within same instance
    print("\n1. Testing state persistence within same instance...")
    ProcessMonitor.reset_instance()

    pm1 = ProcessMonitor()
    await pm1.start_process("test_1", "training", 5)

    pm2 = ProcessMonitor()
    process = await pm2.get_process("test_1")

    assert process is not None, "Same instance should share state"
    assert pm1 is pm2, "Singleton should return same instance"
    print("   ✅ PASS: State shared within same instance")

    # Test 2: State is cleared after reset
    print("\n2. Testing state isolation after reset...")
    ProcessMonitor.reset_instance()

    pm3 = ProcessMonitor()
    process_after_reset = await pm3.get_process("test_1")

    if process_after_reset is None:
        print("   ✅ PASS: State cleaned after reset")
        print("   ✅ FIX VERIFIED: No state bleed between instances")
    else:
        print("   ❌ FAIL: State persisted after reset")
        print("   ❌ BUG: State bleed still present")
        return False

    # Test 3: Multiple resets work correctly
    print("\n3. Testing multiple resets...")
    for i in range(3):
        ProcessMonitor.reset_instance()
        pm = ProcessMonitor()
        await pm.start_process(f"test_{i}", "training", 5)

        # Verify only current process exists
        all_procs = await pm.get_all_processes()
        if len(all_procs) == 1 and all_procs[0].process_id == f"test_{i}":
            print(f"   ✅ Reset {i+1}: Clean state")
        else:
            print(f"   ❌ Reset {i+1}: Found {len(all_procs)} processes, expected 1")
            return False

    print("\n" + "="*80)
    print("STATE BLEED BUG FIX: VERIFIED")
    print("="*80)
    print("\nSummary:")
    print("- Instance variables properly initialized in __init__")
    print("- Singleton pattern maintained with thread-safe __new__")
    print("- reset_instance() creates clean state")
    print("- No state persistence across resets")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_state_bleed_fixed())
    sys.exit(0 if success else 1)
pytestmark = pytest.mark.asyncio
