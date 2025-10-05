"""Tests for model training"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.trainer import get_model_config
from models.experiments import get_recipe_config


class TestModelConfig:
    """Test model configuration"""

    def test_lightgbm_config(self):
        """Test LightGBM configuration"""
        config = get_model_config("lightgbm", {})

        assert config["class"] == "LGBModel"
        assert "kwargs" in config
        assert "learning_rate" in config["kwargs"]

    def test_lstm_config(self):
        """Test LSTM configuration"""
        config = get_model_config("lstm", {})

        assert config["class"] == "LSTM"
        assert config["kwargs"]["hidden_size"] == 64

    def test_custom_params(self):
        """Test custom parameters override"""
        config = get_model_config("lightgbm", {"learning_rate": 0.1})

        assert config["kwargs"]["learning_rate"] == 0.1


class TestRecipes:
    """Test experiment recipes"""

    def test_beginner_recipe(self):
        """Test beginner recipe"""
        recipe = get_recipe_config("beginner_lightgbm")

        assert recipe["feature_handler"] == "alpha158"
        assert len(recipe["models"]) == 1
        assert recipe["models"][0]["handler"] == "lightgbm"

    def test_expert_recipe(self):
        """Test expert ensemble recipe"""
        recipe = get_recipe_config("expert_ensemble")

        assert len(recipe["models"]) > 1
        assert recipe["feature_handler"] == "alpha158"
