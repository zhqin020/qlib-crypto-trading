"""In-process end-to-end checks for the ProcessMonitor API and WebSocket feeds."""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from src.ui.api_enhanced import app
from src.monitoring.process_monitor import ProcessMonitor, monitor, ProcessStatus
from src.utils.qlib_state import clear_qlib_cache
from src.ui.security import VALID_API_KEYS


@pytest.fixture(scope="function", autouse=True)
async def reset_monitor():
    """Ensure a clean ProcessMonitor state for every test."""
    ProcessMonitor.reset_instance()
    clear_qlib_cache()
    yield
    ProcessMonitor.reset_instance()
    clear_qlib_cache()


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def api_key():
    return next(iter(VALID_API_KEYS))


def test_health_endpoint(api_client):
    response = api_client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"


def test_process_list_endpoint(api_client):
    response = api_client.get("/api/processes")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["processes"] == []


def test_process_lifecycle_over_http(api_client):
    async def _create_process():
        proc = await monitor.start_process("training_test", "training", total_steps=2)
        await monitor.update_progress("training_test", 50.0, "Halfway", 1)
        await monitor.complete_process("training_test", {"result": "ok"})
        return proc

    asyncio.run(_create_process())

    response = api_client.get("/api/processes/training_test")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ProcessStatus.COMPLETED.value
    assert payload["metrics"]["progress_percent"] == 100.0


def test_websocket_process_stream(api_client, api_key):
    async def _seed_process():
        await monitor.start_process("ws_test", "training", total_steps=1)
    asyncio.run(_seed_process())

    with api_client.websocket_connect(f"/ws/processes?api_key={api_key}") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "process_update"
        processes = message["processes"]
        assert any(proc["process_id"] == "ws_test" for proc in processes)


def test_websocket_specific_process(api_client, api_key):
    asyncio.run(monitor.start_process("ws_specific", "training", total_steps=1))

    with api_client.websocket_connect(f"/ws/processes/ws_specific?api_key={api_key}") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "process_update"
        assert message["data"]["process_id"] == "ws_specific"
        assert message["data"]["status"] == ProcessStatus.RUNNING.value

        # Complete the process and verify completion message is delivered
        asyncio.run(monitor.complete_process("ws_specific", {"result": "ok"}))

        # Allow for an intermediate update before completion event
        for _ in range(2):
            message = websocket.receive_json()
            if message["type"] == "process_update" and message["data"]["status"] == ProcessStatus.COMPLETED.value:
                continue
            assert message["type"] == "process_complete"
            break
