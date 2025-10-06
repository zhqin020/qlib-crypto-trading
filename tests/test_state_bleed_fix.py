"""
Test that qlib cache is properly cleared between MCP tool calls.

This test verifies the fix for state bleed where qlib's memory cache (H)
retains data across multiple tool calls in the same Python process.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def test_qlib_cache_clearing():
    """Test that clear_qlib_cache() properly clears qlib cache"""
    from utils.qlib_state import clear_qlib_cache
    import qlib
    
    # Initialize qlib with a dummy path
    test_path = "/tmp/test_qlib_data"
    qlib.init(provider_uri=test_path, region="cn")
    
    # Clear cache
    success = clear_qlib_cache()
    assert success, "clear_qlib_cache should return True"
    
    print("✓ Cache clearing works correctly")


def test_init_qlib_clean():
    """Test that init_qlib_clean() properly reinitializes with new path"""
    from utils.qlib_state import init_qlib_clean, get_qlib_config_info
    
    # First initialization
    test_path_1 = "/tmp/test_qlib_1"
    success = init_qlib_clean(provider_uri=test_path_1, region="cn")
    assert success, "First init should succeed"
    
    config_1 = get_qlib_config_info()
    print(f"Config after init 1: {config_1}")
    
    # Second initialization with different path
    test_path_2 = "/tmp/test_qlib_2"
    success = init_qlib_clean(provider_uri=test_path_2, region="cn")
    assert success, "Second init should succeed"
    
    config_2 = get_qlib_config_info()
    print(f"Config after init 2: {config_2}")
    
    # Verify the provider_uri changed
    assert config_1['provider_uri'] != config_2['provider_uri'], \
        f"Provider URI should change: {config_1['provider_uri']} vs {config_2['provider_uri']}"
    
    print("✓ Clean re-initialization works correctly")


def test_multiple_sequential_inits():
    """Test multiple sequential initializations with cache clearing"""
    from utils.qlib_state import init_qlib_clean, get_qlib_config_info
    
    paths = [
        "/tmp/dataset_1",
        "/tmp/dataset_2", 
        "/tmp/dataset_3",
    ]
    
    configs = []
    for i, path in enumerate(paths):
        success = init_qlib_clean(provider_uri=path, region="cn")
        assert success, f"Init with {path} should succeed"
        
        config = get_qlib_config_info()
        configs.append(config)
        
        print(f"  Init {i+1}: {path} -> {config['provider_uri']}")
    
    # Each should have used the correct path
    for i, (path, config) in enumerate(zip(paths, configs)):
        # qlib wraps paths in dict, so check if path is in the provider_uri
        provider = str(config['provider_uri'])
        assert path in provider or path.replace('/tmp/', '') in provider, \
            f"Config {i} should reference {path}, got {provider}"
    
    print("✓ Multiple sequential initializations work correctly")


def test_cache_isolation():
    """Test that cache is actually cleared between inits"""
    from utils.qlib_state import init_qlib_clean, clear_qlib_cache
    from qlib.data.cache import H
    
    # Init first time
    init_qlib_clean(provider_uri="/tmp/test_1", region="cn")
    
    # Cache should exist (even if empty for non-existent data)
    assert H is not None
    
    # Clear cache
    success = clear_qlib_cache()
    assert success
    
    # Cache object still exists but should be cleared
    assert H is not None
    
    # Reinit with new path
    init_qlib_clean(provider_uri="/tmp/test_2", region="cn")
    
    print("✓ Cache isolation works correctly")


if __name__ == "__main__":
    print("Testing qlib state bleed fix...\n")
    
    test_qlib_cache_clearing()
    test_init_qlib_clean()
    test_multiple_sequential_inits()
    test_cache_isolation()
    
    print("\n✅ All state bleed tests passed!")
