"""
Comprehensive tests for GPU/CPU device management in trainer.py
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDeviceManager:
    """Tests for DeviceManager class"""

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=2)
    def test_get_device_auto_with_cuda(self, mock_device_count, mock_is_available):
        """Test auto device selection when CUDA is available"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("auto")

        assert device_type == "cuda"
        assert device_index == 0

    @patch('torch.cuda.is_available', return_value=False)
    def test_get_device_auto_without_cuda(self, mock_is_available):
        """Test auto device selection when CUDA is not available"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("auto")

        assert device_type == "cpu"
        assert device_index == -1

    def test_get_device_explicit_cpu(self):
        """Test explicit CPU device selection"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("cpu")

        assert device_type == "cpu"
        assert device_index == -1

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=2)
    @patch('torch.cuda.get_device_name', return_value="GPU 0")
    def test_get_device_cuda_without_index(self, mock_name, mock_count, mock_available):
        """Test CUDA device selection without index"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("cuda")

        assert device_type == "cuda"
        assert device_index == 0

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=4)
    @patch('torch.cuda.get_device_name', return_value="GPU 2")
    def test_get_device_cuda_with_valid_index(self, mock_name, mock_count, mock_available):
        """Test CUDA device selection with valid index"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("cuda:2")

        assert device_type == "cuda"
        assert device_index == 2

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=2)
    @patch('torch.cuda.get_device_name', return_value="GPU 0")
    def test_get_device_cuda_with_invalid_index(self, mock_name, mock_count, mock_available):
        """Test CUDA device selection with invalid index (too high)"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("cuda:5")

        # Should fall back to cuda:0
        assert device_type == "cuda"
        assert device_index == 0

    @patch('torch.cuda.is_available', return_value=False)
    def test_get_device_cuda_not_available(self, mock_available):
        """Test CUDA request when CUDA not available"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("cuda:0")

        # Should fall back to CPU
        assert device_type == "cpu"
        assert device_index == -1

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=1)
    @patch('torch.cuda.get_device_name', return_value="GPU 0")
    def test_get_device_invalid_format(self, mock_name, mock_count, mock_available):
        """Test invalid device format"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("cuda:invalid")

        # Should fall back to cuda:0
        assert device_type == "cuda"
        assert device_index == 0

    @patch('torch.cuda.is_available', return_value=False)
    def test_get_device_unknown_string(self, mock_available):
        """Test unknown device string"""
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("gpu")

        # Should fall back to auto, then CPU
        assert device_type == "cpu"
        assert device_index == -1

    @patch.dict('sys.modules', {'torch': None})
    def test_get_device_no_torch(self):
        """Test device selection when PyTorch not available"""
        # Force reimport to trigger ImportError
        import importlib
        import src.models.trainer
        importlib.reload(src.models.trainer)
        from src.models.trainer import DeviceManager

        device_type, device_index = DeviceManager.get_device("auto")

        assert device_type == "cpu"
        assert device_index == -1

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=2)
    @patch('torch.cuda.get_device_name', return_value="GPU 1")
    def test_get_device_config_cuda(self, mock_name, mock_count, mock_available):
        """Test device config generation for CUDA"""
        from src.models.trainer import DeviceManager

        config = DeviceManager.get_device_config("cuda:1")

        assert config == {"GPU": 1}

    def test_get_device_config_cpu(self):
        """Test device config generation for CPU"""
        from src.models.trainer import DeviceManager

        config = DeviceManager.get_device_config("cpu")

        assert config == {"GPU": None}

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.device_count', return_value=2)
    @patch('torch.cuda.memory_allocated', side_effect=[1024**3, 2 * 1024**3])
    @patch('torch.cuda.memory_reserved', side_effect=[1.5 * 1024**3, 3 * 1024**3])
    def test_log_memory_usage_with_cuda(self, mock_reserved, mock_allocated, mock_count, mock_available):
        """Test memory logging with CUDA available"""
        from src.models.trainer import DeviceManager

        # Should not raise exception
        DeviceManager.log_memory_usage()

        assert mock_allocated.call_count == 2
        assert mock_reserved.call_count == 2

    @patch('torch.cuda.is_available', return_value=False)
    def test_log_memory_usage_without_cuda(self, mock_available):
        """Test memory logging without CUDA"""
        from src.models.trainer import DeviceManager

        # Should not raise exception
        DeviceManager.log_memory_usage()

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.empty_cache')
    def test_clear_memory_with_cuda(self, mock_empty_cache, mock_available):
        """Test memory clearing with CUDA"""
        from src.models.trainer import DeviceManager

        DeviceManager.clear_memory()

        mock_empty_cache.assert_called_once()

    @patch('torch.cuda.is_available', return_value=False)
    def test_clear_memory_without_cuda(self, mock_available):
        """Test memory clearing without CUDA"""
        from src.models.trainer import DeviceManager

        # Should not raise exception
        DeviceManager.clear_memory()

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.empty_cache', side_effect=RuntimeError("Some error"))
    def test_clear_memory_error_handling(self, mock_empty_cache, mock_available):
        """Test memory clearing handles errors gracefully"""
        from src.models.trainer import DeviceManager

        # Should not raise exception
        DeviceManager.clear_memory()


class TestGetModelConfig:
    """Tests for get_model_config function"""

    def test_lightgbm_config(self):
        """Test LightGBM model config"""
        from src.models.trainer import get_model_config

        config = get_model_config("lightgbm", {}, None)

        assert config["class"] == "LGBModel"
        assert config["module_path"] == "qlib.contrib.model.gbdt"
        assert "GPU" not in config["kwargs"]  # LightGBM doesn't use GPU param

    def test_xgboost_config(self):
        """Test XGBoost model config"""
        from src.models.trainer import get_model_config

        config = get_model_config("xgboost", {}, None)

        assert config["class"] == "XGBModel"
        assert config["module_path"] == "qlib.contrib.model.xgboost"
        assert "GPU" not in config["kwargs"]  # XGBoost doesn't use GPU param

    def test_lstm_config_with_device(self):
        """Test LSTM config with device configuration"""
        from src.models.trainer import get_model_config

        device_config = {"GPU": 0}
        config = get_model_config("lstm", {}, device_config)

        assert config["class"] == "LSTM"
        assert config["module_path"] == "qlib.contrib.model.pytorch_lstm"
        assert config["kwargs"]["GPU"] == 0

    def test_lstm_config_with_cpu_device(self):
        """Test LSTM config with CPU device"""
        from src.models.trainer import get_model_config

        device_config = {"GPU": None}
        config = get_model_config("lstm", {}, device_config)

        assert config["class"] == "LSTM"
        assert config["kwargs"]["GPU"] is None

    def test_transformer_config_with_device(self):
        """Test Transformer config with device"""
        from src.models.trainer import get_model_config

        device_config = {"GPU": 1}
        config = get_model_config("transformer", {}, device_config)

        assert config["class"] == "Transformer"
        assert config["module_path"] == "qlib.contrib.model.pytorch_transformer"
        assert config["kwargs"]["GPU"] == 1

    def test_gru_config_with_device(self):
        """Test GRU config with device"""
        from src.models.trainer import get_model_config

        device_config = {"GPU": 2}
        config = get_model_config("gru", {}, device_config)

        assert config["class"] == "GRU"
        assert config["module_path"] == "qlib.contrib.model.pytorch_gru"
        assert config["kwargs"]["GPU"] == 2

    def test_user_params_override(self):
        """Test user parameters override defaults"""
        from src.models.trainer import get_model_config

        params = {"batch_size": 1024, "lr": 0.01}
        device_config = {"GPU": 0}
        config = get_model_config("lstm", params, device_config)

        assert config["kwargs"]["batch_size"] == 1024
        assert config["kwargs"]["lr"] == 0.01
        assert config["kwargs"]["GPU"] == 0

    def test_user_gpu_override(self):
        """Test user can override GPU parameter"""
        from src.models.trainer import get_model_config

        params = {"GPU": 3}
        device_config = {"GPU": 0}
        config = get_model_config("lstm", params, device_config)

        # User-specified GPU should be used
        assert config["kwargs"]["GPU"] == 3

    def test_device_param_filtered(self):
        """Test device parameter is filtered from params"""
        from src.models.trainer import get_model_config

        params = {"device": "cuda:0", "batch_size": 256}
        device_config = {"GPU": 0}
        config = get_model_config("lstm", params, device_config)

        # device should not appear in kwargs
        assert "device" not in config["kwargs"]
        assert config["kwargs"]["batch_size"] == 256
        assert config["kwargs"]["GPU"] == 0

    def test_unknown_handler_defaults_to_lightgbm(self):
        """Test unknown handler defaults to LightGBM"""
        from src.models.trainer import get_model_config

        config = get_model_config("unknown_model", {}, None)

        assert config["class"] == "LGBModel"


class TestOOMErrorHandling:
    """Tests for OOM error handling"""

    def test_handle_oom_error_decorator_success(self):
        """Test decorator allows successful execution"""
        from src.models.trainer import handle_oom_error

        @handle_oom_error
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.empty_cache')
    def test_handle_oom_error_cuda_oom(self, mock_empty_cache, mock_available):
        """Test decorator handles CUDA OOM error"""
        from src.models.trainer import handle_oom_error

        call_count = [0]

        @handle_oom_error
        def oom_func():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
            return "success after retry"

        result = oom_func()

        # Should succeed after clearing cache and retrying
        assert result == "success after retry"
        assert call_count[0] == 2
        mock_empty_cache.assert_called_once()

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.empty_cache')
    def test_handle_oom_error_persistent_oom(self, mock_empty_cache, mock_available):
        """Test decorator handles persistent OOM error"""
        from src.models.trainer import handle_oom_error

        @handle_oom_error
        def persistent_oom_func():
            raise RuntimeError("CUDA out of memory. Tried to allocate 10.00 GiB")

        with pytest.raises(RuntimeError) as exc_info:
            persistent_oom_func()

        assert "CUDA Out of Memory" in str(exc_info.value)
        assert "batch_size" in str(exc_info.value)
        mock_empty_cache.assert_called_once()

    def test_handle_oom_error_non_oom_error(self):
        """Test decorator doesn't interfere with non-OOM errors"""
        from src.models.trainer import handle_oom_error

        @handle_oom_error
        def other_error_func():
            raise ValueError("Some other error")

        with pytest.raises(ValueError) as exc_info:
            other_error_func()

        assert "Some other error" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
