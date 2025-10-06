"""
Custom 24/7 Calendar Provider for Cryptocurrency Markets

Based on Qlib's CalendarProvider interface, this implements a calendar
for 24/7 trading markets like cryptocurrency exchanges.
"""

import pandas as pd
from typing import List
from pathlib import Path
from qlib.data.cache import H
from qlib.data import CalendarProvider
from qlib.log import get_module_logger

logger = get_module_logger("Crypto24x7CalendarProvider")


class Crypto24x7CalendarProvider(CalendarProvider):
    """
    Calendar provider for 24/7 cryptocurrency markets.

    Unlike stock markets with trading hours and holidays, crypto markets
    operate continuously 24 hours a day, 7 days a week, 365 days a year.
    """

    def __init__(self):
        super().__init__()
        self._calendar_cache = {}

    def calendar(
        self,
        start_time=None,
        end_time=None,
        freq="day",
        future=False,
    ) -> List[pd.Timestamp]:
        """
        Get calendar timestamps for crypto markets (24/7).

        Args:
            start_time: Start time
            end_time: End time
            freq: Frequency ('day', 'hour', 'minute')
            future: Whether to include future dates

        Returns:
            List of timestamps covering the date range
        """
        cache_key = f"{start_time}_{end_time}_{freq}_{future}"

        if cache_key in self._calendar_cache:
            return self._calendar_cache[cache_key]

        # Default to a wide range if not specified
        if start_time is None:
            start_time = pd.Timestamp("2010-01-01")
        if end_time is None:
            end_time = pd.Timestamp.now() if not future else pd.Timestamp("2030-12-31")

        # Convert to timestamps
        start_time = pd.Timestamp(start_time)
        end_time = pd.Timestamp(end_time)

        # Generate continuous calendar based on frequency
        if freq.lower() in ['d', 'day', 'daily', '1d']:
            # Daily: Every day including weekends
            calendar = pd.date_range(start=start_time, end=end_time, freq='D')
        elif freq.lower() in ['h', 'hour', 'hourly', '1h']:
            # Hourly: Every hour of every day
            calendar = pd.date_range(start=start_time, end=end_time, freq='H')
        elif freq.lower() in ['m', 'min', 'minute', '1m', '5m', '15m', '30m']:
            # Minute level
            if '5' in freq:
                calendar = pd.date_range(start=start_time, end=end_time, freq='5min')
            elif '15' in freq:
                calendar = pd.date_range(start=start_time, end=end_time, freq='15min')
            elif '30' in freq:
                calendar = pd.date_range(start=start_time, end=end_time, freq='30min')
            else:
                calendar = pd.date_range(start=start_time, end=end_time, freq='min')
        else:
            # Default to daily
            calendar = pd.date_range(start=start_time, end=end_time, freq='D')

        # Convert to list of timestamps
        result = calendar.tolist()

        # Cache the result
        self._calendar_cache[cache_key] = result

        logger.info(f"Generated {len(result)} timestamps for crypto calendar ({freq}) from {start_time} to {end_time}")

        return result

    def locate_index(self, start_time, end_time, freq, future=False):
        """
        Locate the indices of start_time and end_time in calendar.

        Returns:
            Tuple of (start_index, end_index)
        """
        cal = self.calendar(start_time=start_time, end_time=end_time, freq=freq, future=future)

        start_time = pd.Timestamp(start_time)
        end_time = pd.Timestamp(end_time)

        # Find closest indices
        start_idx = 0
        end_idx = len(cal) - 1

        for i, ts in enumerate(cal):
            if ts >= start_time and start_idx == 0:
                start_idx = i
            if ts <= end_time:
                end_idx = i

        return start_idx, end_idx

    def load_calendar(self, freq, future=False):
        """
        Load calendar timestamps from cache or generate new ones.

        For crypto, we generate continuous timestamps without gaps.
        """
        # Generate wide range calendar
        start = pd.Timestamp("2010-01-01")
        end = pd.Timestamp.now() if not future else pd.Timestamp("2030-12-31")

        return self.calendar(start_time=start, end_time=end, freq=freq, future=future)


def register_crypto_calendar():
    """
    Register the crypto 24/7 calendar provider with Qlib.

    Call this before qlib.init() to use crypto calendar.
    """
    from qlib.config import C

    # Create instance
    crypto_cal = Crypto24x7CalendarProvider()

    # Register as calendar provider
    C.set(calendar_provider=crypto_cal)

    logger.info("Registered Crypto24x7CalendarProvider for 24/7 trading")

    return crypto_cal
