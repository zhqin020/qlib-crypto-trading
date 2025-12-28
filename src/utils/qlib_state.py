"""
Qlib State Management Utilities

This module provides utilities to properly reset qlib's global state
between tool calls in the MCP server to prevent state bleed.

The key insight: qlib.init() can be called multiple times and it will
reinitialize. The main issue is the CACHE (H) which persists data from
previous runs. We clear that before each init.
"""
import asyncio
import logging
from .logging_config import get_logger
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Union, Dict, Any, AsyncIterator, Callable

logger = get_logger(__name__)

# Global async lock to prevent concurrent qlib initialization
_init_lock = asyncio.Lock()


def clear_qlib_cache():
    """
    Clear qlib's memory cache (H) to prevent data bleed.
    
    This is the primary source of state bleed - the cache stores
    calendar, instruments, and features data that persists across
    qlib.init() calls.
    """
    try:
        from qlib.data.cache import H
        
        logger.info("Clearing qlib cache (H)...")
        H.clear()
        logger.info("Successfully cleared qlib cache")
        return True
        
    except ImportError:
        logger.warning("qlib not imported yet, skipping cache clear")
        return False
    except Exception as e:
        logger.error(f"Error clearing qlib cache: {e}", exc_info=True)
        return False


def init_qlib_clean(
    provider_uri: Union[str, Path, Dict[str, str]],
    region: str = "cn",
    **kwargs
) -> bool:
    """
    Initialize qlib with clean cache.

    Clears the cache before initializing to ensure each tool call
    uses fresh data from the specified provider_uri.

    Args:
        provider_uri: Path to qlib data or dict mapping freq->path
        region: Market region (default: "cn" for crypto/custom)
        **kwargs: Additional qlib.init() parameters

    Returns:
        True if initialization successful, False otherwise
    """
    try:
        import qlib

        # Register 24/7 crypto calendar BEFORE qlib.init()
        # This must happen before init to ensure crypto calendar is available
        try:
            from data_pipeline.crypto_calendar_provider import register_crypto_calendar
            register_crypto_calendar()
            logger.info("Crypto calendar registered")
        except Exception as e:
            logger.warning(f"Could not register crypto calendar: {e}")

        # Clear cache before init to prevent data bleed
        success = clear_qlib_cache()
        if not success:
            logger.error("Failed to clear qlib cache before init")
            return False
        
        # Convert Path to string if needed
        if isinstance(provider_uri, Path):
            provider_uri = str(provider_uri)
        
        # Initialize qlib - it handles re-initialization internally
        # Disable caching by default to prevent cross-contamination
        init_kwargs = {
            'provider_uri': provider_uri,
            'region': region,
            'expression_cache': None,  # Disable expression cache
            'dataset_cache': None,     # Disable dataset cache
        }
        init_kwargs.update(kwargs)
        
        logger.info(f"Initializing qlib with provider_uri: {provider_uri}")
        qlib.init(**init_kwargs)
        logger.info("Qlib initialized successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize qlib: {e}", exc_info=True)
        return False


@asynccontextmanager
async def qlib_init_context(
    provider_uri: Union[str, Path, Dict[str, str]],
    region: str = "cn",
    **kwargs
) -> AsyncIterator[None]:
    """
    Acquire the global qlib init lock, perform a clean init, and hold the
    lock for the caller until the critical section completes.

    This ensures that callers can safely run post-initialization work under
    mutual exclusion (e.g. qlib.fetch operations, cache-inspected logic) so
    tests that assert serialization observe the expected ordering.
    """
    async with _init_lock:
        logger.info("Acquired init lock, proceeding with qlib initialization")
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            lambda: init_qlib_clean(provider_uri, region, **kwargs)
        )
        if not success:
            raise RuntimeError("Failed to initialize qlib")
        logger.info("Qlib initialization complete; entering critical section")
        try:
            yield
        finally:
            clear_qlib_cache()
            logger.info("Released qlib init critical section and cleared cache")


async def init_qlib_clean_async(
    provider_uri: Union[str, Path, Dict[str, str]],
    region: str = "cn",
    **kwargs
) -> bool:
    """Convenience wrapper that performs init without exposing the context."""
    async with qlib_init_context(provider_uri, region, **kwargs):
        return True


def get_qlib_config_info() -> Dict[str, Any]:
    """
    Get current qlib configuration for debugging.

    Returns:
        Dictionary with current qlib config state
    """
    try:
        import qlib
        from qlib.config import C

        # Safely get attributes
        def safe_get(attr, default='Not set'):
            try:
                return getattr(C, attr, default)
            except (KeyError, AttributeError):
                return default

        info = {
            'provider_uri': safe_get('provider_uri'),
            'region': safe_get('region'),
            'cache_enabled': {
                'expression': safe_get('expression_cache', 'Unknown'),
                'dataset': safe_get('dataset_cache', 'Unknown'),
            }
        }
        return info
    except Exception as e:
        return {'error': str(e)}
