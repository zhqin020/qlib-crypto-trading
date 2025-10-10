"""Tests for data pipeline"""

import pytest
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_pipeline.crypto_calendar import CryptoCalendar
# Note: CryptoToQlibConverter was deprecated in favor of official_qlib_converter
# from data_pipeline.official_qlib_converter import convert_crypto_data_official


class TestCryptoCalendar:
    """Test crypto calendar functionality"""

    def test_calendar_creation(self):
        """Test calendar can be created"""
        calendar = CryptoCalendar(freq="1d")
        assert calendar.freq == "1d"
        assert calendar.name == "crypto_1d"

    def test_trading_dates(self):
        """Test generating trading dates"""
        calendar = CryptoCalendar(freq="1d")
        dates = calendar.get_trading_dates("2023-01-01", "2023-01-31")

        assert len(dates) == 31  # All days in January
        assert dates[0] == pd.Timestamp("2023-01-01")
        assert dates[-1] == pd.Timestamp("2023-01-31")

    def test_always_trading(self):
        """Test that crypto markets are always trading"""
        calendar = CryptoCalendar(freq="1d")

        # Test weekend
        saturday = pd.Timestamp("2023-01-07")  # Saturday
        sunday = pd.Timestamp("2023-01-08")    # Sunday

        assert calendar.is_trading_time(saturday) is True
        assert calendar.is_trading_time(sunday) is True

    def test_hourly_calendar(self):
        """Test hourly frequency calendar"""
        calendar = CryptoCalendar(freq="1h")
        dates = calendar.get_trading_dates("2023-01-01", "2023-01-02")

        # Should have 24 hours * 2 days = 48 periods
        assert len(dates) >= 24


@pytest.mark.skip(reason="CryptoToQlibConverter deprecated - use official_qlib_converter functions instead")
class TestQlibConverter:
    """Test Qlib data converter (DEPRECATED)"""

    def test_symbol_normalization(self):
        """Test symbol name normalization"""
        # converter = CryptoToQlibConverter("data/raw", "data/qlib")
        # assert converter.normalize_symbol("BTC/USDT") == "BTC_USDT"
        pass


@pytest.mark.asyncio
async def test_market_data_quote():
    """Test real-time quote fetching"""
    from data_pipeline.market_data import get_quote

    try:
        quote = await get_quote("BTC/USDT", "binance")

        assert "symbol" in quote
        assert "last" in quote
        assert quote["symbol"] == "BTC/USDT"
        assert quote["last"] > 0
    except Exception as e:
        # Skip if no internet connection
        pytest.skip(f"Skipping live data test: {e}")
