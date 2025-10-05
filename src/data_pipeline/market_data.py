"""
Market Data Provider for Cryptocurrency
Supports multiple exchanges via CCXT
"""

import asyncio
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Exchange instances cache
_exchanges: Dict[str, ccxt.Exchange] = {}


def get_exchange(provider: str = "binance") -> ccxt.Exchange:
    """Get or create exchange instance"""
    if provider not in _exchanges:
        exchange_class = getattr(ccxt, provider)
        _exchanges[provider] = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    return _exchanges[provider]


async def get_quote(symbol: str, provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Get real-time quote for a crypto symbol

    Args:
        symbol: Trading pair (e.g., 'BTC/USDT')
        provider: Exchange name (binance, kraken, coinbase)

    Returns:
        Quote data with price, volume, bid, ask, etc.
    """
    try:
        provider = provider or "binance"
        exchange = get_exchange(provider)

        ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)

        return {
            "symbol": symbol,
            "provider": provider,
            "timestamp": ticker.get('timestamp'),
            "datetime": ticker.get('datetime'),
            "last": ticker.get('last'),
            "bid": ticker.get('bid'),
            "ask": ticker.get('ask'),
            "high": ticker.get('high'),
            "low": ticker.get('low'),
            "volume": ticker.get('baseVolume'),
            "quote_volume": ticker.get('quoteVolume'),
        }
    except Exception as e:
        logger.error(f"Error fetching quote for {symbol}: {e}")
        raise


async def get_quotes_batch(symbols: List[str], provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get quotes for multiple symbols in parallel"""
    provider = provider or "binance"
    tasks = [get_quote(symbol, provider) for symbol in symbols]
    return await asyncio.gather(*tasks, return_exceptions=True)


async def get_historical(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "1d",
    provider: Optional[str] = None
) -> pd.DataFrame:
    """
    Get historical OHLCV data

    Args:
        symbol: Trading pair
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        provider: Exchange name

    Returns:
        DataFrame with OHLCV data
    """
    try:
        provider = provider or "binance"
        exchange = get_exchange(provider)

        # Convert dates to timestamps
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        all_candles = []
        current_ts = start_ts

        # Fetch in batches (most exchanges limit to 1000 candles per request)
        while current_ts < end_ts:
            candles = await asyncio.to_thread(
                exchange.fetch_ohlcv,
                symbol,
                timeframe=interval,
                since=current_ts,
                limit=1000
            )

            if not candles:
                break

            all_candles.extend(candles)
            current_ts = candles[-1][0] + 1

            # Rate limiting
            await asyncio.sleep(exchange.rateLimit / 1000)

        # Convert to DataFrame
        df = pd.DataFrame(
            all_candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)

        # Filter to exact date range
        df = df[(df.index >= start_date) & (df.index <= end_date)]

        logger.info(f"Fetched {len(df)} candles for {symbol} from {start_date} to {end_date}")

        return df

    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        raise


async def subscribe(symbols: List[str], fields: List[str] = None, update_interval: int = 1) -> Dict[str, Any]:
    """
    Subscribe to real-time market data

    Note: This is a placeholder. Real implementation would use WebSocket connections
    """
    fields = fields or ["price"]

    return {
        "status": "subscribed",
        "symbols": symbols,
        "fields": fields,
        "update_interval": update_interval,
        "message": "Subscription created. Use WebSocket endpoint ws://localhost:5100/ws/market-data"
    }


async def download_crypto_universe(
    symbols: List[str],
    start_date: str,
    end_date: str,
    interval: str = "1d",
    provider: str = "binance",
    output_dir: str = None
) -> pd.DataFrame:
    """
    Download historical data for multiple cryptocurrencies

    Args:
        symbols: List of trading pairs
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Timeframe
        provider: Exchange name
        output_dir: Directory to save CSV files

    Returns:
        Combined DataFrame with all symbols
    """
    from pathlib import Path

    output_dir = output_dir or "data/raw"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_data = {}

    for symbol in symbols:
        try:
            logger.info(f"Downloading {symbol}...")
            df = await get_historical(symbol, start_date, end_date, interval, provider)

            # Normalize symbol name for filename
            symbol_name = symbol.replace("/", "_")

            # Save to CSV
            csv_path = output_path / f"{symbol_name}_{interval}.csv"
            df.to_csv(csv_path)
            logger.info(f"Saved {symbol} to {csv_path}")

            all_data[symbol] = df

        except Exception as e:
            logger.error(f"Failed to download {symbol}: {e}")
            continue

    return all_data
