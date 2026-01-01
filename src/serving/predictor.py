import pickle
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

import qlib
from qlib.utils import init_instance_by_config
from qlib.data.dataset import DatasetH

logger = logging.getLogger("Predictor")

class QlibPredictor:
    """
    Handles model loading and inference for live trading.
    """
    def __init__(self, model_path: Union[str, Path], feature_config: Optional[Dict[str, Any]] = None):
        self.model_path = Path(model_path)
        self.feature_config = feature_config
        self.model = None
        
        self._load_model()
        
    def _load_model(self):
        """Load the pickled Qlib model."""
        if not self.model_path.exists():
            logger.error(f"Model file not found: {self.model_path}")
            raise FileNotFoundError(f"Model not found at {self.model_path}")
            
        logger.info(f"Loading model from {self.model_path}")
        try:
            with open(self.model_path, "rb") as f:
                logger.debug("Model file opened, starting pickle.load...")
                self.model = pickle.load(f)
                logger.debug("pickle.load finished.")
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}", exc_info=True)
            raise

    def predict(self, dataset: DatasetH) -> pd.Series:
        """
        Predict scores using the loaded model and a Qlib Dataset.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded.")
            
        logger.info("Starting model inference...")
        try:
            # Debug dataset shape
            df = dataset.prepare("test", col_set="feature")
            logger.debug(f"Dataset feature shape: {df.shape}")
            logger.debug(f"Dataset columns: {df.columns.tolist()[:5]}... (total {len(df.columns)})")
        except:
            pass
            
        scores = self.model.predict(dataset)
        
        # Qlib predict usually returns a Series with [datetime, symbol] index
        if isinstance(scores, pd.DataFrame):
            # Sometimes it returns a DataFrame with one column
            scores = scores.iloc[:, 0]
            
        return scores

    @classmethod
    def from_meta(cls, meta_path: Union[str, Path]):
        """
        Create a predictor from a metadata file.
        """
        meta_path = Path(meta_path)
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)
            
        model_path = Path(meta["model_path"])
        # If model_path in meta is relative, we might need to resolve it
        if not model_path.is_absolute():
            model_path = meta_path.parent / model_path.name
            
        return cls(model_path)
