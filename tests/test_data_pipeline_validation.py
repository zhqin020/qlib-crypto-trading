"""
Comprehensive tests for data pipeline input validation
Tests all validation functions and their integration into pipeline modules
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from src.data_pipeline.validation import (
    validate_dataset_name,
    validate_date_range,
    validate_symbol,
    validate_symbols,
    validate_calendar,
    validate_handler,
    validate_file_path,
    validate_interval,
    validate_provider,
    ValidationError
)


class TestDatasetNameValidation:
    """Test validate_dataset_name function"""

    def test_valid_dataset_names(self):
        """Test valid dataset names"""
        valid_names = [
            "crypto_btc",
            "test_dataset",
            "dataset-123",
            "BTC_DAILY",
            "a",
            "A" * 100  # Max length
        ]
        for name in valid_names:
            result = validate_dataset_name(name)
            assert result == name

    def test_empty_dataset_name(self):
        """Test empty dataset name"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_dataset_name("")

    def test_invalid_type(self):
        """Test non-string dataset name"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_dataset_name(123)

    def test_too_long(self):
        """Test dataset name too long"""
        with pytest.raises(ValidationError, match="too long"):
            validate_dataset_name("a" * 101)

    def test_invalid_characters(self):
        """Test invalid characters"""
        invalid_names = [
            "dataset/name",
            "dataset\\name",
            "dataset.name",
            "dataset name",
            "dataset@name",
            "dataset#name"
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError, match="invalid characters"):
                validate_dataset_name(name)

    def test_path_traversal_attempts(self):
        """Test path traversal prevention"""
        # Note: These are caught by invalid characters check first (/ and .)
        traversal_attempts = [
            "../dataset",
            "dataset/../other",
            "../../etc/passwd",
            "dataset/subdir"
        ]
        for name in traversal_attempts:
            with pytest.raises(ValidationError):
                validate_dataset_name(name)

    def test_shell_metacharacters(self):
        """Test shell metacharacter prevention"""
        # Note: These are caught by invalid characters check first
        shell_attempts = [
            "dataset; rm -rf /",
            "dataset$(whoami)",
            "dataset`ls`",
            "dataset|cat",
            "dataset&echo"
        ]
        for name in shell_attempts:
            with pytest.raises(ValidationError):
                validate_dataset_name(name)


class TestDateRangeValidation:
    """Test validate_date_range function"""

    def test_valid_date_ranges(self):
        """Test valid date ranges"""
        start_dt, end_dt = validate_date_range("2020-01-01", "2020-12-31")
        assert start_dt == datetime(2020, 1, 1)
        assert end_dt == datetime(2020, 12, 31)

    def test_none_values(self):
        """Test None values use defaults"""
        start_dt, end_dt = validate_date_range(None, None)
        assert start_dt == datetime(2019, 1, 1)
        assert end_dt.date() == datetime.now().date()

    def test_invalid_format(self):
        """Test invalid date format"""
        with pytest.raises(ValidationError, match="Invalid date format"):
            validate_date_range("2020/01/01", "2020/12/31")

        with pytest.raises(ValidationError, match="Invalid date format"):
            validate_date_range("01-01-2020", "12-31-2020")

    def test_start_after_end(self):
        """Test start date after end date"""
        with pytest.raises(ValidationError, match="must be before"):
            validate_date_range("2020-12-31", "2020-01-01")

    def test_start_equals_end(self):
        """Test start date equals end date"""
        with pytest.raises(ValidationError, match="must be before"):
            validate_date_range("2020-01-01", "2020-01-01")

    def test_too_far_past(self):
        """Test date too far in the past"""
        with pytest.raises(ValidationError, match="too far in the past"):
            validate_date_range("1999-01-01", "2020-01-01")

    def test_future_date(self):
        """Test future date"""
        future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        with pytest.raises(ValidationError, match="cannot be in the future"):
            validate_date_range("2020-01-01", future_date)

    def test_range_too_large(self):
        """Test date range too large"""
        with pytest.raises(ValidationError, match="too large"):
            validate_date_range("2000-01-01", "2025-01-01")


class TestSymbolValidation:
    """Test validate_symbol and validate_symbols functions"""

    def test_valid_symbols(self):
        """Test valid trading symbols"""
        valid_symbols = [
            "BTC/USDT",
            "ETH/BTC",
            "AAPL",
            "BTC",
            "BTCUSDT"
        ]
        for symbol in valid_symbols:
            result = validate_symbol(symbol)
            assert result == symbol.upper()

    def test_empty_symbol(self):
        """Test empty symbol"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_symbol("")

    def test_invalid_type(self):
        """Test non-string symbol"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_symbol(123)

    def test_too_long(self):
        """Test symbol too long"""
        with pytest.raises(ValidationError, match="too long"):
            validate_symbol("A" * 21)

    def test_too_short(self):
        """Test symbol too short"""
        with pytest.raises(ValidationError, match="too short"):
            validate_symbol("A")

    def test_invalid_characters(self):
        """Test invalid characters in symbol"""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_symbol("BTC-USDT")

        with pytest.raises(ValidationError, match="invalid characters"):
            validate_symbol("BTC.USDT")

    def test_invalid_pair_format(self):
        """Test invalid pair format"""
        with pytest.raises(ValidationError, match="Invalid pair format"):
            validate_symbol("BTC/USDT/ETH")

        with pytest.raises(ValidationError, match="Invalid pair format"):
            validate_symbol("BTC/")

        with pytest.raises(ValidationError, match="Invalid pair format"):
            validate_symbol("/USDT")

    def test_validate_symbols_list(self):
        """Test validate_symbols with valid list"""
        symbols = ["BTC/USDT", "ETH/BTC", "LTC/USDT"]
        result = validate_symbols(symbols)
        assert len(result) == 3
        assert all(s == s.upper() for s in result)

    def test_validate_symbols_empty_list(self):
        """Test validate_symbols with empty list"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_symbols([])

    def test_validate_symbols_not_list(self):
        """Test validate_symbols with non-list"""
        with pytest.raises(ValidationError, match="must be a list"):
            validate_symbols("BTC/USDT")

    def test_validate_symbols_too_many(self):
        """Test validate_symbols with too many symbols"""
        symbols = [f"SYM{i}" for i in range(1001)]
        with pytest.raises(ValidationError, match="Too many symbols"):
            validate_symbols(symbols)

    def test_validate_symbols_filters_invalid(self):
        """Test validate_symbols filters out invalid symbols"""
        symbols = ["BTC/USDT", "INVALID-SYMBOL", "ETH/BTC"]
        result = validate_symbols(symbols)
        assert len(result) == 2
        assert "BTC/USDT" in result
        assert "ETH/BTC" in result

    def test_validate_symbols_all_invalid(self):
        """Test validate_symbols with all invalid symbols"""
        symbols = ["INVALID-1", "INVALID-2", "INVALID-3"]
        with pytest.raises(ValidationError, match="No valid symbols"):
            validate_symbols(symbols)


class TestCalendarValidation:
    """Test validate_calendar function"""

    def test_valid_calendars(self):
        """Test valid calendar names"""
        valid_calendars = [
            "crypto_1d",
            "crypto_1h",
            "crypto_1m",
            "crypto_daily",
            "crypto_hourly",
            "stock_1d"
        ]
        for calendar in valid_calendars:
            result = validate_calendar(calendar)
            assert result == calendar

    def test_empty_calendar(self):
        """Test empty calendar"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_calendar("")

    def test_invalid_type(self):
        """Test non-string calendar"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_calendar(123)

    def test_too_long(self):
        """Test calendar name too long"""
        with pytest.raises(ValidationError, match="too long"):
            validate_calendar("a" * 51)

    def test_invalid_characters(self):
        """Test invalid characters in calendar"""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_calendar("crypto-1d")

        with pytest.raises(ValidationError, match="invalid characters"):
            validate_calendar("crypto.1d")


class TestHandlerValidation:
    """Test validate_handler function"""

    def test_valid_handlers(self):
        """Test valid handler names"""
        valid_handlers = ["alpha158", "alpha360", "custom", "CustomHandler"]
        for handler in valid_handlers:
            result = validate_handler(handler)
            assert result == handler

    def test_empty_handler(self):
        """Test empty handler"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_handler("")

    def test_invalid_type(self):
        """Test non-string handler"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_handler(123)

    def test_too_long(self):
        """Test handler name too long"""
        with pytest.raises(ValidationError, match="too long"):
            validate_handler("a" * 101)

    def test_invalid_characters(self):
        """Test invalid characters in handler"""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_handler("alpha-158")

        with pytest.raises(ValidationError, match="invalid characters"):
            validate_handler("alpha.158")


class TestFilePathValidation:
    """Test validate_file_path function"""

    def test_valid_existing_file(self):
        """Test valid existing file"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            file_path = f.name

        try:
            result = validate_file_path(file_path, must_exist=True)
            assert result.exists()
        finally:
            Path(file_path).unlink()

    def test_valid_nonexisting_file(self):
        """Test valid non-existing file"""
        file_path = "/tmp/nonexistent_file.csv"
        result = validate_file_path(file_path, must_exist=False)
        assert isinstance(result, Path)

    def test_empty_path(self):
        """Test empty file path"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_file_path("")

    def test_invalid_type(self):
        """Test non-string file path"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_file_path(123)

    def test_file_must_exist(self):
        """Test file must exist"""
        with pytest.raises(ValidationError, match="does not exist"):
            validate_file_path("/tmp/nonexistent_file_xyz_123.csv", must_exist=True)


class TestIntervalValidation:
    """Test validate_interval function"""

    def test_valid_intervals(self):
        """Test valid intervals"""
        valid_intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
        for interval in valid_intervals:
            result = validate_interval(interval)
            assert result == interval

    def test_empty_interval(self):
        """Test empty interval"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_interval("")

    def test_invalid_type(self):
        """Test non-string interval"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_interval(123)

    def test_invalid_interval(self):
        """Test invalid interval"""
        with pytest.raises(ValidationError, match="Invalid interval"):
            validate_interval("2m")

        with pytest.raises(ValidationError, match="Invalid interval"):
            validate_interval("10h")


class TestProviderValidation:
    """Test validate_provider function"""

    def test_valid_providers(self):
        """Test valid provider names"""
        valid_providers = ["binance", "kraken", "coinbase", "bybit"]
        for provider in valid_providers:
            result = validate_provider(provider)
            assert result == provider.lower()

    def test_case_normalization(self):
        """Test provider name is normalized to lowercase"""
        result = validate_provider("BINANCE")
        assert result == "binance"

    def test_empty_provider(self):
        """Test empty provider"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_provider("")

    def test_invalid_type(self):
        """Test non-string provider"""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_provider(123)

    def test_too_long(self):
        """Test provider name too long"""
        with pytest.raises(ValidationError, match="too long"):
            validate_provider("a" * 51)

    def test_invalid_characters(self):
        """Test invalid characters in provider"""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_provider("binance-us")

        with pytest.raises(ValidationError, match="invalid characters"):
            validate_provider("binance.com")


class TestIntegrationValidation:
    """Test validation integration in pipeline modules"""

    @pytest.mark.asyncio
    async def test_snapshot_validation_integration(self):
        """Test validation in snapshot.create_snapshot"""
        from src.data_pipeline.snapshot import create_snapshot

        # Test with invalid dataset name
        result = await create_snapshot(
            dataset="../etc/passwd",
            calendar="crypto_1d"
        )
        assert "error" in result
        assert "Invalid input" in result["error"]

    @pytest.mark.asyncio
    async def test_market_data_validation_integration(self):
        """Test validation in market_data functions"""
        try:
            from src.data_pipeline.market_data import get_quote

            # Test with invalid symbol
            with pytest.raises(ValidationError):
                await get_quote("INVALID-SYMBOL")
        except ImportError:
            pytest.skip("ccxt not installed")

    @pytest.mark.asyncio
    async def test_features_validation_integration(self):
        """Test validation in features.create_feature_set"""
        from src.data_pipeline.features import create_feature_set

        # Test with invalid dataset name
        result = await create_feature_set(
            dataset_ref="../etc/passwd",
            handler="alpha158"
        )
        assert "error" in result
        assert "Invalid input" in result["error"]

    def test_converter_validation_integration(self):
        """Test validation in official_qlib_converter"""
        try:
            from src.data_pipeline.official_qlib_converter import convert_crypto_data_official

            # Test with empty csv_dir
            with pytest.raises(ValueError, match="must be a non-empty string"):
                convert_crypto_data_official("", "output", "1d")

            # Test with invalid frequency
            with pytest.raises(ValueError, match="Invalid frequency format"):
                convert_crypto_data_official("input", "output", "invalid")
        except ImportError:
            pytest.skip("psutil not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
