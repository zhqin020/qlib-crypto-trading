"""Tests for REST API"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.api import app


client = TestClient(app)


class TestAPIEndpoints:
    """Test API endpoints"""

    def test_root(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Qlib Crypto Trading Platform" in response.text

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_list_datasets(self):
        """Test listing datasets"""
        response = client.get("/api/datasets")
        assert response.status_code == 200
        assert "datasets" in response.json()

    def test_list_models(self):
        """Test listing models"""
        response = client.get("/api/models")
        assert response.status_code == 200
        assert "models" in response.json()

    def test_list_backtests(self):
        """Test listing backtests"""
        response = client.get("/api/backtests")
        assert response.status_code == 200
        assert "backtests" in response.json()

    def test_list_predictions(self):
        """Test listing predictions"""
        response = client.get("/api/predictions")
        assert response.status_code == 200
        assert "predictions" in response.json()
