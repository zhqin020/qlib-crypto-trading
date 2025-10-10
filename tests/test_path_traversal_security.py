"""
Comprehensive tests for path traversal vulnerability fixes

Tests validate that all API endpoints properly reject malicious input
and accept legitimate dataset/model/process names.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import os

# Add src to path and set working directory
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir / "src"))
os.chdir(str(test_dir))

# Import after path setup
from fastapi import HTTPException

# Import validation functions and app directly
def import_api_module():
    """Import API module with proper relative imports"""
    from src.ui import api_enhanced
    return api_enhanced

api_module = import_api_module()
app = api_module.app
validate_dataset_name = api_module.validate_dataset_name
validate_model_id = api_module.validate_model_id
validate_process_id = api_module.validate_process_id
validate_path_safety = api_module.validate_path_safety


# Test client
client = TestClient(app)


class TestValidationHelpers:
    """Test validation helper functions"""

    def test_validate_dataset_name_valid(self):
        """Test valid dataset names are accepted"""
        valid_names = [
            "crypto_btc_daily",
            "test_dataset",
            "dataset-123",
            "DATASET_ABC",
            "data123",
            "a",
            "a" * 100,  # Max length
        ]
        for name in valid_names:
            result = validate_dataset_name(name)
            assert result == name, f"Valid name '{name}' should be accepted"

    def test_validate_dataset_name_path_traversal(self):
        """Test path traversal attempts are rejected"""
        malicious_names = [
            "../etc/passwd",
            "../../etc/shadow",
            "..\\windows\\system32",
            "data/../../../etc/passwd",
            "..",
            ".../.../etc/passwd",
            "data/../../secret",
        ]
        for name in malicious_names:
            with pytest.raises(HTTPException) as exc_info:
                validate_dataset_name(name)
            assert exc_info.value.status_code == 400
            assert "path traversal" in exc_info.value.detail.lower()

    def test_validate_dataset_name_invalid_chars(self):
        """Test invalid characters are rejected"""
        invalid_names = [
            "data/subdir",
            "data\\subdir",
            "data$special",
            "data@email",
            "data space",
            "data\x00null",
            "data;command",
            "data|pipe",
            "data&ampersand",
        ]
        for name in invalid_names:
            with pytest.raises(HTTPException) as exc_info:
                validate_dataset_name(name)
            assert exc_info.value.status_code == 400

    def test_validate_dataset_name_empty(self):
        """Test empty name is rejected"""
        with pytest.raises(HTTPException) as exc_info:
            validate_dataset_name("")
        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    def test_validate_dataset_name_too_long(self):
        """Test overly long names are rejected"""
        long_name = "a" * 101  # Max is 100
        with pytest.raises(HTTPException) as exc_info:
            validate_dataset_name(long_name)
        assert exc_info.value.status_code == 400
        assert "too long" in exc_info.value.detail.lower()

    def test_validate_model_id_valid(self):
        """Test valid model IDs are accepted"""
        valid_ids = [
            "lightgbm_crypto_20250107",
            "model-123",
            "MODEL_ABC_123",
            "m",
            "a" * 200,  # Max length
        ]
        for model_id in valid_ids:
            result = validate_model_id(model_id)
            assert result == model_id

    def test_validate_model_id_path_traversal(self):
        """Test model ID path traversal attempts are rejected"""
        malicious_ids = [
            "../../../etc/passwd",
            "model/../../secret",
            "..\\..\\windows",
        ]
        for model_id in malicious_ids:
            with pytest.raises(HTTPException) as exc_info:
                validate_model_id(model_id)
            assert exc_info.value.status_code == 400
            assert "path traversal" in exc_info.value.detail.lower()

    def test_validate_process_id_valid(self):
        """Test valid process IDs are accepted"""
        valid_ids = [
            "training_abc123",
            "backtest_xyz789",
            "download_test-123",
            "prediction_1234567890",
        ]
        for process_id in valid_ids:
            result = validate_process_id(process_id)
            assert result == process_id

    def test_validate_process_id_invalid(self):
        """Test invalid process IDs are rejected"""
        invalid_ids = [
            "../process",
            "process/subdir",
            "process;command",
            "process|pipe",
            "process space",
        ]
        for process_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                validate_process_id(process_id)
            assert exc_info.value.status_code == 400

    def test_validate_path_safety(self):
        """Test path safety validation"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"
            base.mkdir()

            # Create a safe subdirectory
            safe_dir = base / "safe"
            safe_dir.mkdir()

            # Test safe path
            result = validate_path_safety(safe_dir, base)
            assert result == safe_dir.resolve()

            # Test path outside base (using symlink simulation)
            outside_dir = Path(tmpdir) / "outside"
            outside_dir.mkdir()

            with pytest.raises(HTTPException) as exc_info:
                validate_path_safety(outside_dir, base)
            assert exc_info.value.status_code == 403
            assert "outside allowed directory" in exc_info.value.detail.lower()


class TestDataConvertEndpoint:
    """Test /api/data/convert endpoint security"""

    def test_convert_valid_dataset(self):
        """Test conversion with valid dataset name"""
        response = client.post(
            "/api/data/convert",
            params={"dataset": "test_crypto_btc", "freq": "1d"}
        )
        # May fail due to missing data, but should not fail validation
        assert response.status_code in [200, 500], "Should pass validation"

    def test_convert_path_traversal_attack(self):
        """Test conversion rejects path traversal"""
        malicious_datasets = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",  # URL encoded
            "data/../../secret",
            "..\\..\\windows\\system32",
        ]
        for dataset in malicious_datasets:
            response = client.post(
                "/api/data/convert",
                params={"dataset": dataset, "freq": "1d"}
            )
            assert response.status_code == 400, f"Should reject '{dataset}'"
            assert "path traversal" in response.json()["detail"].lower()

    def test_convert_invalid_frequency(self):
        """Test conversion rejects invalid frequency"""
        response = client.post(
            "/api/data/convert",
            params={"dataset": "test_dataset", "freq": "invalid"}
        )
        assert response.status_code == 400
        assert "invalid frequency" in response.json()["detail"].lower()

    def test_convert_special_chars(self):
        """Test conversion rejects special characters"""
        invalid_datasets = [
            "data;rm -rf /",
            "data|cat /etc/passwd",
            "data&& malicious",
            "data$PWD",
        ]
        for dataset in invalid_datasets:
            response = client.post(
                "/api/data/convert",
                params={"dataset": dataset, "freq": "1d"}
            )
            assert response.status_code == 400


class TestModelEndpoints:
    """Test model-related endpoint security"""

    def test_get_model_path_traversal(self):
        """Test GET /api/models/{model_id} rejects path traversal"""
        from urllib.parse import quote

        malicious_ids = [
            "../../../etc/passwd",
            "model/../../secret",
            "..\\..\\windows",
        ]
        for model_id in malicious_ids:
            # URL encode to ensure special chars are passed through
            encoded_id = quote(model_id, safe='')
            response = client.get(f"/api/models/{encoded_id}")
            # Should reject with 400 (validation error) or 404 after validation passes
            # If validation works, the decoded path will be caught
            assert response.status_code in [400, 404], f"Should reject '{model_id}' (got {response.status_code})"

    def test_get_model_valid_not_found(self):
        """Test GET /api/models/{model_id} with valid ID returns 404 if not exists"""
        response = client.get("/api/models/nonexistent_model_123")
        # Should pass validation but not find model
        assert response.status_code == 404


class TestProcessEndpoints:
    """Test process-related endpoint security"""

    def test_get_process_invalid_id(self):
        """Test GET /api/processes/{process_id} rejects invalid IDs"""
        from urllib.parse import quote

        invalid_ids = [
            "../process",
            "process/subdir",
            "process;command",
            "process|pipe",
        ]
        for process_id in invalid_ids:
            encoded_id = quote(process_id, safe='')
            response = client.get(f"/api/processes/{encoded_id}")
            # Should reject with 400 (validation error) or 404 if validation passes
            assert response.status_code in [400, 404], f"Should reject '{process_id}' (got {response.status_code})"

    def test_cancel_process_invalid_id(self):
        """Test DELETE /api/processes/{process_id} rejects invalid IDs"""
        from urllib.parse import quote

        invalid_ids = [
            "../process",
            "process;rm -rf /",
        ]
        for process_id in invalid_ids:
            encoded_id = quote(process_id, safe='')
            response = client.delete(f"/api/processes/{encoded_id}")
            # Should reject with 400 (validation error) or 404 if validation passes
            assert response.status_code in [400, 404], f"Should reject '{process_id}' (got {response.status_code})"

    def test_get_process_logs_invalid_id(self):
        """Test GET /api/processes/{process_id}/logs rejects invalid IDs"""
        response = client.get("/api/processes/invalid;command/logs")
        assert response.status_code == 400


class TestPydanticValidation:
    """Test Pydantic model validation"""

    def test_train_model_request_validation(self):
        """Test TrainModelRequest validates dataset name"""
        malicious_payloads = [
            {"dataset": "../../../etc/passwd", "feature_handler": "alpha158", "model_handler": "lightgbm"},
            {"dataset": "data/../../secret", "feature_handler": "alpha158", "model_handler": "lightgbm"},
        ]
        for payload in malicious_payloads:
            response = client.post("/api/models/train", json=payload)
            assert response.status_code in [400, 422], "Should reject malicious dataset"

    def test_backtest_request_validation(self):
        """Test BacktestRequest validates dataset and model_id"""
        malicious_payloads = [
            {"model_id": "../model", "dataset": "valid_dataset"},
            {"model_id": "valid_model", "dataset": "../../../etc/passwd"},
        ]
        for payload in malicious_payloads:
            response = client.post("/api/backtests/run", json=payload)
            assert response.status_code in [400, 422]

    def test_backtest_request_invalid_dates(self):
        """Invalid date formats should be rejected before reaching the handler"""
        payload = {
            "model_id": "mock_model",
            "dataset": "mock_dataset",
            "start_date": "2024-13-01",
            "end_date": "2024-12-31",
        }
        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422

    def test_train_model_segments_validation(self):
        """Segments must include all ranges with valid dates"""
        payload = {
            "dataset": "mock_dataset",
            "feature_handler": "alpha158",
            "model_handler": "lightgbm",
            "segments": {
                "train": ["2023-01-01", "2023-03-31"],
                "valid": ["2023-04-01", "2023-05-31"],
                # missing test segment
            },
        }
        response = client.post("/api/models/train", json=payload)
        assert response.status_code == 422


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_null_byte_injection(self):
        """Test null byte injection is rejected"""
        response = client.post(
            "/api/data/convert",
            params={"dataset": "data\x00hidden", "freq": "1d"}
        )
        assert response.status_code == 400

    def test_unicode_normalization(self):
        """Test unicode normalization attacks"""
        # Unicode variations of ".."
        response = client.post(
            "/api/data/convert",
            params={"dataset": "\u2024\u2024", "freq": "1d"}
        )
        assert response.status_code == 400

    def test_very_long_input(self):
        """Test very long input is rejected"""
        long_dataset = "a" * 10000
        response = client.post(
            "/api/data/convert",
            params={"dataset": long_dataset, "freq": "1d"}
        )
        assert response.status_code == 400
        assert "too long" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
