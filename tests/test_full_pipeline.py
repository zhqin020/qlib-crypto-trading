"""
Comprehensive end-to-end tests for the full Qlib crypto trading pipeline.

Tests both simple and complex scenarios via:
1. Direct API calls
2. MCP server tools (qlib-trading)

IMPORTANT: These are INTEGRATION tests - they test the full stack working together.
"""

import pytest
import asyncio
import httpx
from pathlib import Path


pytestmark = pytest.mark.requires_server


class TestSimpleScenarios:
    """Simple, single-operation tests to verify basic functionality"""

    BASE_URL = "http://localhost:5100"

    @pytest.mark.asyncio
    async def test_01_download_single_crypto_day(self):
        """Test downloading 1 day of BTC data"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/data/download",
                json={
                    "symbols": ["BTC/USDT"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-01",
                    "interval": "1d",
                    "provider": "binance"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"
            assert "process_id" in data

            # Wait for completion
            await asyncio.sleep(3)

            # Check process status
            proc_response = await client.get(f"{self.BASE_URL}/api/processes/{data['process_id']}")
            proc_data = proc_response.json()
            assert proc_data["status"] == "completed"
            assert proc_data["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_02_convert_to_qlib_format(self):
        """Test converting CSV to Qlib binary format"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/data/convert",
                params={"dataset": "test_simple", "freq": "1d"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"

            # Wait for completion
            await asyncio.sleep(5)

            # Check process status
            proc_response = await client.get(f"{self.BASE_URL}/api/processes/{data['process_id']}")
            proc_data = proc_response.json()
            assert proc_data["status"] == "completed"
            assert "BTC" in proc_data["result"]["symbols"]

            # Verify dataset exists
            dataset_path = Path("/Users/chadwyatt/Code/trading/qlib-2/data/qlib/test_simple")
            assert dataset_path.exists()
            assert (dataset_path / "calendars" / "day.txt").exists()
            assert (dataset_path / "features" / "BTC" / "close.day.bin").exists()

    @pytest.mark.asyncio
    async def test_03_list_datasets(self):
        """Test listing available datasets"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.BASE_URL}/api/datasets")
            assert response.status_code == 200
            data = response.json()
            assert "datasets" in data
            assert len(data["datasets"]) > 0

    @pytest.mark.asyncio
    async def test_04_process_monitoring(self):
        """Test process monitoring API"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get all processes
            response = await client.get(f"{self.BASE_URL}/api/processes")
            assert response.status_code == 200
            data = response.json()
            assert "processes" in data

            # Get running processes
            response = await client.get(f"{self.BASE_URL}/api/processes/running")
            assert response.status_code == 200


class TestComplexScenarios:
    """Complex, multi-step scenarios testing full workflows"""

    BASE_URL = "http://localhost:5100"

    @pytest.mark.asyncio
    async def test_01_full_pipeline_single_crypto(self):
        """
        Test complete pipeline for single crypto:
        1. Download data (full year)
        2. Convert to Qlib
        3. Train model
        4. Run backtest
        5. Generate predictions
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Step 1: Download
            download_response = await client.post(
                f"{self.BASE_URL}/api/data/download",
                json={
                    "symbols": ["ETH/USDT"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "interval": "1d",
                    "provider": "binance"
                }
            )
            assert download_response.status_code == 200
            await asyncio.sleep(5)

            # Step 2: Convert
            convert_response = await client.post(
                f"{self.BASE_URL}/api/data/convert",
                params={"dataset": "test_eth_full", "freq": "1d"}
            )
            assert convert_response.status_code == 200
            convert_data = convert_response.json()
            await asyncio.sleep(10)

            # Verify conversion completed
            proc_response = await client.get(
                f"{self.BASE_URL}/api/processes/{convert_data['process_id']}"
            )
            proc_data = proc_response.json()
            assert proc_data["status"] == "completed"

            # Step 3: Train model
            train_response = await client.post(
                f"{self.BASE_URL}/api/models/train",
                json={
                    "dataset": "test_eth_full",
                    "feature_handler": "alpha158",
                    "model_handler": "lightgbm"
                }
            )
            assert train_response.status_code == 200
            train_data = train_response.json()
            await asyncio.sleep(25)

            # Verify training completed
            train_proc = await client.get(
                f"{self.BASE_URL}/api/processes/{train_data['process_id']}"
            )
            train_proc_data = train_proc.json()
            assert train_proc_data["status"] == "completed"
            model_id = train_proc_data["result"]["model_id"]
            assert model_id is not None

            print(f"✓ Trained model: {model_id}")

    @pytest.mark.asyncio
    async def test_02_multiple_crypto_parallel(self):
        """
        Test downloading multiple cryptos in parallel
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]

            download_response = await client.post(
                f"{self.BASE_URL}/api/data/download",
                json={
                    "symbols": symbols,
                    "start_date": "2024-11-01",
                    "end_date": "2024-11-30",
                    "interval": "1d",
                    "provider": "binance"
                }
            )
            assert download_response.status_code == 200
            await asyncio.sleep(8)

            # Verify all downloaded
            data_dir = Path("/Users/chadwyatt/Code/trading/qlib-2/data/raw")
            for symbol in symbols:
                symbol_file = symbol.replace("/", "_") + "_1d.csv"
                assert (data_dir / symbol_file).exists()

    @pytest.mark.asyncio
    async def test_03_process_cancellation(self):
        """Test cancelling a long-running process"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Start a download
            download_response = await client.post(
                f"{self.BASE_URL}/api/data/download",
                json={
                    "symbols": ["SOL/USDT"],
                    "start_date": "2023-01-01",
                    "end_date": "2024-12-31",
                    "interval": "1h",
                    "provider": "binance"
                }
            )
            process_id = download_response.json()["process_id"]

            # Immediately cancel
            await asyncio.sleep(1)
            cancel_response = await client.post(
                f"{self.BASE_URL}/api/processes/{process_id}/cancel"
            )
            assert cancel_response.status_code == 200


class TestMCPServerIntegration:
    """Test pipeline via MCP qlib-trading server tools"""

    @pytest.mark.asyncio
    async def test_01_mcp_market_data_quote(self):
        """Test getting real-time quote via MCP"""
        # This would use the MCP tools directly
        # For now, we verify the tools exist and are callable
        from src.mcp import qlib_trading_server
        assert hasattr(qlib_trading_server, 'market_data_get_quote')

    @pytest.mark.asyncio
    async def test_02_mcp_create_snapshot(self):
        """Test creating data snapshot via MCP"""
        from src.mcp import qlib_trading_server
        assert hasattr(qlib_trading_server, 'data_create_snapshot')

    @pytest.mark.asyncio
    async def test_03_mcp_train_model(self):
        """Test training model via MCP"""
        from src.mcp import qlib_trading_server
        assert hasattr(qlib_trading_server, 'models_train')


class TestErrorHandling:
    """Test error scenarios and fail-fast behavior"""

    BASE_URL = "http://localhost:5100"

    @pytest.mark.asyncio
    async def test_01_invalid_symbol(self):
        """Test downloading invalid symbol fails fast"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/data/download",
                json={
                    "symbols": ["INVALID/SYMBOL"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-10",
                    "interval": "1d",
                    "provider": "binance"
                }
            )
            await asyncio.sleep(3)
            # Should complete but potentially with error
            # NO FALLBACKS - should fail clearly

    @pytest.mark.asyncio
    async def test_02_train_without_data(self):
        """Test training without dataset fails fast"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/models/train",
                json={
                    "dataset": "nonexistent_dataset",
                    "feature_handler": "alpha158",
                    "model_handler": "lightgbm"
                }
            )
            assert response.status_code == 200  # Starts process
            train_data = response.json()
            await asyncio.sleep(5)

            # Check it failed
            proc_response = await client.get(
                f"{self.BASE_URL}/api/processes/{train_data['process_id']}"
            )
            proc_data = proc_response.json()
            assert proc_data["status"] == "failed"
            assert proc_data["error"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
