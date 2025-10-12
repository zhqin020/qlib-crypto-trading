from datetime import datetime

import pytest

from src.data_pipeline.data_refresh import DataRefreshConfig, run_data_refresh


def test_data_refresh_config_disabled(monkeypatch):
    monkeypatch.setenv("DATA_REFRESH_ENABLED", "false")
    monkeypatch.delenv("DATA_REFRESH_SYMBOLS", raising=False)

    config = DataRefreshConfig.from_env()

    assert config.enabled is False
    assert config.active is False
    assert config.symbols == []


def test_data_refresh_config_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_REFRESH_ENABLED", "true")
    monkeypatch.setenv("DATA_REFRESH_SYMBOLS", "BTC/USDT, ETH/USDT")
    monkeypatch.setenv("DATA_REFRESH_INTERVAL", "1h")
    monkeypatch.setenv("DATA_REFRESH_LOOKBACK_DAYS", "7")
    monkeypatch.setenv("DATA_REFRESH_FREQUENCY_MINUTES", "45")
    monkeypatch.setenv("DATA_REFRESH_PROVIDER", "kraken")
    monkeypatch.setenv("DATA_REFRESH_DATASET", "crypto_test")
    monkeypatch.setenv("DATA_REFRESH_CALENDAR", "crypto_1h")
    monkeypatch.setenv("DATA_REFRESH_OUTPUT_DIR", str(tmp_path))

    config = DataRefreshConfig.from_env()

    assert config.enabled is True
    assert config.active is True
    assert config.symbols == ["BTC/USDT", "ETH/USDT"]
    assert config.interval == "1h"
    assert config.lookback_days == 7
    assert config.frequency_minutes == 45
    assert config.provider == "kraken"
    assert config.dataset == "crypto_test"
    assert config.calendar == "crypto_1h"
    assert str(config.output_dir) == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_run_data_refresh_success(monkeypatch, tmp_path):
    config = DataRefreshConfig(
        enabled=True,
        symbols=["BTC/USDT", "ETH/USDT"],
        interval="1d",
        lookback_days=7,
        frequency_minutes=60,
        provider="binance",
        dataset="crypto",
        calendar="crypto_1d",
        output_dir=tmp_path,
    )

    calls = {}

    async def fake_download(*, symbols, start_date, end_date, interval, provider, output_dir):
        calls["download"] = {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval,
            "provider": provider,
            "output_dir": output_dir,
        }

    async def fake_snapshot(*, dataset, calendar, start, end):
        calls["snapshot"] = {
            "dataset": dataset,
            "calendar": calendar,
            "start": start,
            "end": end,
        }
        return {"status": "ready"}

    now = datetime(2025, 1, 10)

    result = await run_data_refresh(
        config,
        now=now,
        download_fn=fake_download,
        snapshot_fn=fake_snapshot,
    )

    assert result["status"] == "ok"
    assert result["start_date"] == "2025-01-03"
    assert result["end_date"] == "2025-01-10"
    assert calls["download"]["symbols"] == ["BTC/USDT", "ETH/USDT"]
    assert calls["snapshot"]["dataset"] == "crypto"
    assert calls["snapshot"]["calendar"] == "crypto_1d"
    assert result["kpi_evaluation"]["stage"] == "data_refresh"
    assert result["kpi_evaluation"]["passed"] is True
    assert result["refresh_ready"] is True


@pytest.mark.asyncio
async def test_run_data_refresh_download_failure(tmp_path):
    config = DataRefreshConfig(
        enabled=True,
        symbols=["BTC/USDT"],
        interval="1d",
        lookback_days=1,
        frequency_minutes=60,
        provider="binance",
        dataset="crypto",
        calendar="crypto_1d",
        output_dir=tmp_path,
    )

    async def boom(**kwargs):
        raise RuntimeError("network down")

    result = await run_data_refresh(config, download_fn=boom)

    assert result["status"] == "error"
    assert "download_failed" in result["error"]
    assert result["kpi_evaluation"]["passed"] is False
    assert result["refresh_ready"] is False
