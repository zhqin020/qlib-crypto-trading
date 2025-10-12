"""Automated market data refresh helpers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional

from .market_data import download_crypto_universe
from .snapshot import create_snapshot
from ..analytics.investment_kpis import kpi_registry

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}


def _as_bool(value: str) -> bool:
    return value.strip().lower() in _TRUTHY


def _safe_int(value: str, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _split_symbols(value: str) -> List[str]:
    return [symbol.strip() for symbol in value.split(",") if symbol.strip()]


@dataclass(frozen=True)
class DataRefreshConfig:
    """Configuration for automated market data refresh."""

    enabled: bool
    symbols: List[str]
    interval: str
    lookback_days: int
    frequency_minutes: int
    provider: str
    dataset: str
    calendar: str
    output_dir: Path

    @classmethod
    def from_env(cls) -> "DataRefreshConfig":
        env = os.getenv
        enabled = _as_bool(env("DATA_REFRESH_ENABLED", "false"))
        symbols = _split_symbols(env("DATA_REFRESH_SYMBOLS", ""))
        interval = env("DATA_REFRESH_INTERVAL", "1d")
        lookback_days = _safe_int(env("DATA_REFRESH_LOOKBACK_DAYS", "30"), default=30, minimum=1)
        frequency_minutes = _safe_int(env("DATA_REFRESH_FREQUENCY_MINUTES", "180"), default=180, minimum=5)
        provider = env("DATA_REFRESH_PROVIDER", "binance")
        dataset = env("DATA_REFRESH_DATASET", "crypto")
        calendar = env("DATA_REFRESH_CALENDAR", "crypto_1d")
        output_dir = Path(env("DATA_REFRESH_OUTPUT_DIR", "data/raw")).expanduser().resolve()

        return cls(
            enabled=enabled,
            symbols=symbols,
            interval=interval,
            lookback_days=lookback_days,
            frequency_minutes=frequency_minutes,
            provider=provider,
            dataset=dataset,
            calendar=calendar,
            output_dir=output_dir,
        )

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.symbols)

    @property
    def frequency_seconds(self) -> int:
        return max(self.frequency_minutes, 5) * 60


async def run_data_refresh(
    config: DataRefreshConfig,
    *,
    now: Optional[datetime] = None,
    download_fn: Optional[Callable[..., Awaitable[object]]] = None,
    snapshot_fn: Optional[Callable[..., Awaitable[Dict[str, object]]]] = None,
) -> Dict[str, object]:
    """Execute a single market data refresh cycle."""

    if not config.active:
        return {"status": "disabled"}

    now_dt = (now or datetime.utcnow()).replace(microsecond=0)
    end_date = now_dt.date()
    start_date = (end_date - timedelta(days=config.lookback_days)).isoformat()
    end_date_str = end_date.isoformat()

    data_age_hours = max(
        0.0,
        (now_dt - datetime.strptime(end_date_str, "%Y-%m-%d")).total_seconds() / 3600.0,
    )

    summary: Dict[str, object] = {
        "status": "ok",
        "start_date": start_date,
        "end_date": end_date_str,
        "symbols": list(config.symbols),
        "interval": config.interval,
        "provider": config.provider,
        "dataset": config.dataset,
        "data_age_hours": data_age_hours,
    }

    download = download_fn or download_crypto_universe
    snapshot = snapshot_fn or create_snapshot

    try:
        await download(
            symbols=config.symbols,
            start_date=start_date,
            end_date=end_date_str,
            interval=config.interval,
            provider=config.provider,
            output_dir=str(config.output_dir),
        )
    except Exception as exc:  # pragma: no cover - relies on external services
        logger.error("Market data refresh download failed: %s", exc, exc_info=True)
        summary["status"] = "error"
        summary["error"] = f"download_failed: {exc}"
        evaluation = kpi_registry.record(
            "data_refresh",
            {
                "dataset": config.dataset,
                "provider": config.provider,
                "symbols": config.symbols,
                "error": str(exc),
            },
            {
                "download_success": 0,
                "data_age_hours": data_age_hours,
                "lookback_days": config.lookback_days,
            },
        )
        summary["kpi_evaluation"] = evaluation.to_dict()
        summary["refresh_ready"] = False
        return summary

    try:
        snapshot_result = await snapshot(
            dataset=config.dataset,
            calendar=config.calendar,
            start=start_date,
            end=end_date_str,
        )
        summary["snapshot"] = snapshot_result
        if snapshot_result.get("error"):
            summary["status"] = "error"
            summary["error"] = snapshot_result["error"]
    except Exception as exc:  # pragma: no cover - relies on filesystem + qlib
        logger.error("Market data snapshot creation failed: %s", exc, exc_info=True)
        summary["status"] = "error"
        summary["error"] = f"snapshot_failed: {exc}"

    evaluation = kpi_registry.record(
        "data_refresh",
        {
            "dataset": config.dataset,
            "provider": config.provider,
            "symbols": config.symbols,
        },
        {
            "download_success": 1,
            "data_age_hours": data_age_hours,
            "lookback_days": config.lookback_days,
        },
    )
    summary["kpi_evaluation"] = evaluation.to_dict()
    summary["refresh_ready"] = evaluation.passed

    return summary


__all__ = ["DataRefreshConfig", "run_data_refresh"]
