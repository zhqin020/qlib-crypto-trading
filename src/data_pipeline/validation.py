"""
Comprehensive input validation for data pipeline modules
Prevents injection attacks, path traversal, and invalid data
"""

import re
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when validation fails"""
    pass


def validate_dataset_name(dataset: str) -> str:
    """
    Validate dataset name against path traversal and injection

    Args:
        dataset: Dataset name to validate

    Returns:
        Validated dataset name

    Raises:
        ValidationError: If validation fails
    """
    if not dataset:
        raise ValidationError("Dataset name cannot be empty")

    if not isinstance(dataset, str):
        raise ValidationError("Dataset name must be a string")

    # Check length
    if len(dataset) > 100:
        raise ValidationError("Dataset name too long (max 100 characters)")

    if len(dataset) < 1:
        raise ValidationError("Dataset name too short (min 1 character)")

    # Only alphanumeric, underscore, hyphen allowed
    if not re.match(r'^[a-zA-Z0-9_-]+$', dataset):
        raise ValidationError(
            "Dataset name contains invalid characters. "
            "Only alphanumeric, underscore, and hyphen allowed"
        )

    # No path traversal attempts
    if '..' in dataset or '/' in dataset or '\\' in dataset:
        raise ValidationError("Path traversal patterns not allowed in dataset name")

    # No shell metacharacters
    shell_chars = ['$', '`', ';', '|', '&', '>', '<', '(', ')', '{', '}', '[', ']']
    if any(char in dataset for char in shell_chars):
        raise ValidationError("Shell metacharacters not allowed in dataset name")

    logger.debug(f"Dataset name validated: {dataset}")
    return dataset


def validate_date_range(start: Optional[str], end: Optional[str]) -> Tuple[datetime, datetime]:
    """
    Validate and parse date range

    Args:
        start: Start date string (YYYY-MM-DD) or None
        end: End date string (YYYY-MM-DD) or None

    Returns:
        Tuple of (start_datetime, end_datetime)

    Raises:
        ValidationError: If validation fails
    """
    # Handle None values with defaults
    if start is None:
        start = "2019-01-01"
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    # Validate format
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError as e:
        raise ValidationError(
            f"Invalid date format. Expected YYYY-MM-DD. Error: {str(e)}"
        )

    # Validate range
    if start_dt >= end_dt:
        raise ValidationError(
            f"Start date ({start}) must be before end date ({end})"
        )

    # Validate reasonable bounds
    min_date = datetime(2000, 1, 1)
    if start_dt < min_date:
        raise ValidationError(
            f"Start date ({start}) is too far in the past (before {min_date.strftime('%Y-%m-%d')})"
        )

    max_date = datetime.now() + timedelta(days=1)
    if end_dt > max_date:
        raise ValidationError(
            f"End date ({end}) cannot be in the future"
        )

    # Validate range size (prevent DoS with huge ranges)
    max_years = 10
    if (end_dt - start_dt).days > (max_years * 365):
        raise ValidationError(
            f"Date range too large (max {max_years} years)"
        )

    logger.debug(f"Date range validated: {start} to {end}")
    return start_dt, end_dt


def validate_symbol(symbol: str) -> str:
    """
    Validate a single trading symbol

    Args:
        symbol: Trading symbol (e.g., BTC/USDT)

    Returns:
        Validated and normalized symbol (uppercase)

    Raises:
        ValidationError: If validation fails
    """
    if not symbol:
        raise ValidationError("Symbol cannot be empty")

    if not isinstance(symbol, str):
        raise ValidationError("Symbol must be a string")

    # Normalize to uppercase
    symbol = symbol.upper().strip()

    # Check length
    if len(symbol) > 20:
        raise ValidationError(f"Symbol too long: {symbol} (max 20 characters)")

    if len(symbol) < 2:
        raise ValidationError(f"Symbol too short: {symbol} (min 2 characters)")

    # Only alphanumeric and forward slash allowed (for pairs like BTC/USDT)
    if not re.match(r'^[A-Z0-9/]{2,20}$', symbol):
        raise ValidationError(
            f"Symbol contains invalid characters: {symbol}. "
            "Only alphanumeric and '/' allowed"
        )

    # Validate pair format if contains /
    if '/' in symbol:
        parts = symbol.split('/')
        if len(parts) != 2:
            raise ValidationError(f"Invalid pair format: {symbol}. Expected BASE/QUOTE")
        if not all(part for part in parts):
            raise ValidationError(f"Invalid pair format: {symbol}. Both base and quote required")

    return symbol


def validate_symbols(symbols: List[str], max_count: int = 1000) -> List[str]:
    """
    Validate list of trading symbols

    Args:
        symbols: List of trading symbols
        max_count: Maximum number of symbols allowed

    Returns:
        List of validated symbols (invalid ones filtered out)

    Raises:
        ValidationError: If validation fails
    """
    if not symbols:
        raise ValidationError("Symbol list cannot be empty")

    if not isinstance(symbols, list):
        raise ValidationError("Symbols must be a list")

    # Check count
    if len(symbols) > max_count:
        raise ValidationError(
            f"Too many symbols: {len(symbols)} (max {max_count})"
        )

    validated = []
    errors = []

    for symbol in symbols:
        try:
            validated_symbol = validate_symbol(symbol)
            validated.append(validated_symbol)
        except ValidationError as e:
            logger.warning(f"Skipping invalid symbol {symbol}: {e}")
            errors.append((symbol, str(e)))
            continue

    if not validated:
        raise ValidationError(
            f"No valid symbols after validation. Errors: {errors[:5]}"
        )

    logger.debug(f"Validated {len(validated)}/{len(symbols)} symbols")
    return validated


def validate_calendar(calendar: str) -> str:
    """
    Validate calendar type

    Args:
        calendar: Calendar identifier (e.g., crypto_1d, crypto_1h)

    Returns:
        Validated calendar name

    Raises:
        ValidationError: If validation fails
    """
    if not calendar:
        raise ValidationError("Calendar cannot be empty")

    if not isinstance(calendar, str):
        raise ValidationError("Calendar must be a string")

    # Check length
    if len(calendar) > 50:
        raise ValidationError("Calendar name too long (max 50 characters)")

    # Only alphanumeric, underscore allowed
    if not re.match(r'^[a-zA-Z0-9_]+$', calendar):
        raise ValidationError(
            "Calendar name contains invalid characters. "
            "Only alphanumeric and underscore allowed"
        )

    # Validate known calendar patterns
    valid_patterns = [
        r'^crypto_\d+[mhd]$',  # crypto_1m, crypto_1h, crypto_1d
        r'^crypto_(daily|hourly|minute)$',
        r'^[a-z]+_[a-z0-9_]+$'  # general pattern
    ]

    if not any(re.match(pattern, calendar.lower()) for pattern in valid_patterns):
        logger.warning(f"Calendar {calendar} doesn't match known patterns")

    logger.debug(f"Calendar validated: {calendar}")
    return calendar


def validate_handler(handler: str) -> str:
    """
    Validate feature handler name

    Args:
        handler: Handler identifier (e.g., alpha158, alpha360)

    Returns:
        Validated handler name

    Raises:
        ValidationError: If validation fails
    """
    if not handler:
        raise ValidationError("Handler cannot be empty")

    if not isinstance(handler, str):
        raise ValidationError("Handler must be a string")

    # Check length
    if len(handler) > 100:
        raise ValidationError("Handler name too long (max 100 characters)")

    # Only alphanumeric, underscore allowed
    if not re.match(r'^[a-zA-Z0-9_]+$', handler):
        raise ValidationError(
            "Handler name contains invalid characters. "
            "Only alphanumeric and underscore allowed"
        )

    # Validate known handlers
    known_handlers = {'alpha158', 'alpha360', 'custom'}
    if handler.lower() not in known_handlers:
        logger.warning(
            f"Handler {handler} is not a known type. "
            f"Known types: {known_handlers}"
        )

    logger.debug(f"Handler validated: {handler}")
    return handler


def validate_file_path(file_path: str, must_exist: bool = True) -> Path:
    """
    Validate file path for security

    Args:
        file_path: File path to validate
        must_exist: Whether file must exist

    Returns:
        Validated Path object

    Raises:
        ValidationError: If validation fails
    """
    if not file_path:
        raise ValidationError("File path cannot be empty")

    if not isinstance(file_path, str):
        raise ValidationError("File path must be a string")

    try:
        path = Path(file_path).resolve()
    except Exception as e:
        raise ValidationError(f"Invalid file path: {e}")

    # Check for path traversal attempts
    if '..' in str(file_path):
        logger.warning(f"Path contains '..': {file_path}")

    # Validate file exists if required
    if must_exist and not path.exists():
        raise ValidationError(f"File does not exist: {file_path}")

    # Validate file extension for CSVs
    if path.suffix and path.suffix.lower() not in ['.csv', '.txt', '.json']:
        logger.warning(f"Unusual file extension: {path.suffix}")

    logger.debug(f"File path validated: {path}")
    return path


def validate_interval(interval: str) -> str:
    """
    Validate time interval for market data

    Args:
        interval: Time interval (e.g., 1m, 5m, 1h, 1d)

    Returns:
        Validated interval

    Raises:
        ValidationError: If validation fails
    """
    if not interval:
        raise ValidationError("Interval cannot be empty")

    if not isinstance(interval, str):
        raise ValidationError("Interval must be a string")

    # Valid intervals
    valid_intervals = {
        '1m', '3m', '5m', '15m', '30m',
        '1h', '2h', '4h', '6h', '8h', '12h',
        '1d', '3d', '1w', '1M'
    }

    if interval not in valid_intervals:
        raise ValidationError(
            f"Invalid interval: {interval}. "
            f"Valid intervals: {sorted(valid_intervals)}"
        )

    logger.debug(f"Interval validated: {interval}")
    return interval


def validate_provider(provider: str) -> str:
    """
    Validate exchange provider name

    Args:
        provider: Provider/exchange name

    Returns:
        Validated provider name (lowercase)

    Raises:
        ValidationError: If validation fails
    """
    if not provider:
        raise ValidationError("Provider cannot be empty")

    if not isinstance(provider, str):
        raise ValidationError("Provider must be a string")

    provider = provider.lower().strip()

    # Check length
    if len(provider) > 50:
        raise ValidationError("Provider name too long (max 50 characters)")

    # Only alphanumeric and underscore
    if not re.match(r'^[a-z0-9_]+$', provider):
        raise ValidationError(
            "Provider name contains invalid characters. "
            "Only lowercase alphanumeric and underscore allowed"
        )

    # Known providers
    known_providers = {'binance', 'kraken', 'coinbase', 'bybit', 'okx', 'huobi'}
    if provider not in known_providers:
        logger.warning(
            f"Provider {provider} is not known. "
            f"Known providers: {known_providers}"
        )

    logger.debug(f"Provider validated: {provider}")
    return provider
