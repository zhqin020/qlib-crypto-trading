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
    Supports both single-model (Global) and multi-model (Per-Symbol) modes.
    """
    def __init__(self, model_input: Union[str, Path]):
        self.model_input = Path(model_input)
        self.models: Dict[str, Any] = {}
        self.global_model = None
        
        self._load_models()
        
    def _load_models(self):
        """Load one or more models based on input path."""
        if not self.model_input.exists():
            logger.error(f"Model input not found: {self.model_input}")
            raise FileNotFoundError(f"Model input not found at {self.model_input}")

        if self.model_input.is_file():
            if self.model_input.suffix == ".json":
                # JSON mapping file (symbol -> model_info)
                self._load_from_json(self.model_input)
            else:
                # Single global model
                self.global_model = self._load_single_model(self.model_input)
                logger.info(f"Loaded global model: {self.model_input.name}")
        elif self.model_input.is_dir():
            # Directory of models
            self._load_from_dir(self.model_input)
            
    def _load_single_model(self, path: Path):
        """Load a single pickled model."""
        try:
            with open(path, "rb") as f:
                model = pickle.load(f)
            return model
        except Exception as e:
            logger.error(f"Failed to load model {path}: {e}")
            return None

    def _load_from_json(self, json_path: Path):
        """Load models from a summary JSON mapping."""
        import json
        with open(json_path, "r") as f:
            data = json.load(f)
        
        # summary format: {"symbols": {"BTC": {"model_path": "..."}}}
        symbol_map = data.get("symbols", {})
        for symbol, info in symbol_map.items():
            model_path = Path(info.get("model_path"))
            if not model_path.is_absolute():
                model_path = json_path.parent.parent / model_path
            
            model = self._load_single_model(model_path)
            if model:
                self.models[symbol] = model
                
        logger.info(f"Loaded {len(self.models)} per-symbol models from JSON mapping.")

    def _load_from_dir(self, dir_path: Path):
        """Load all .pkl models in a directory and infer symbol from name."""
        # Expected format: handler_{symbol}_timestamp.pkl
        for pkl_file in dir_path.glob("*.pkl"):
            name = pkl_file.stem
            parts = name.split("_")
            if len(parts) >= 2:
                # heuristic: assuming name contains symbol (e.g., alstm_BTC_...)
                # usually it's handler_symbol_timestamp
                # if it's just handler_timestamp, we might need a better logic
                symbol = parts[1] 
                model = self._load_single_model(pkl_file)
                if model:
                    self.models[symbol] = model
                    
        logger.info(f"Loaded {len(self.models)} per-symbol models from directory {dir_path}")

    def predict(self, dataset: DatasetH) -> pd.Series:
        """
        Predict scores. In multi-model mode, split dataset by symbol.
        """
        # 1. Determine which symbols we are dealing with from the dataset
        try:
            # We get instruments from the dataset segments
            # or just prepare it once to see the index
            df_full = dataset.prepare("test", col_set="feature")
            # Index is (datetime, instrument)
            symbols_in_data = df_full.index.get_level_values(1).unique().tolist()
        except Exception as e:
            logger.error(f"Failed to extract symbols from dataset: {e}")
            symbols_in_data = []

        if not symbols_in_data:
            return pd.Series(dtype=float)

        all_results = []

        for symbol in symbols_in_data:
            # Use specific model or global one
            model = self.models.get(symbol, self.global_model)
            if not model:
                logger.warning(f"No model found for {symbol} and no global model. Skipping.")
                continue
            
            # Subsetting dataset for this symbol
            # We wrap the dataset to force the instrument filter during prepare()
            subset_wrapper = SubsetDatasetWrapper(dataset, symbol)
            
            try:
                preds = model.predict(subset_wrapper)
                if isinstance(preds, pd.DataFrame):
                    preds = preds.iloc[:, 0]
                all_results.append(preds)
            except Exception as e:
                logger.error(f"Prediction failed for {symbol}: {e}")

        if not all_results:
            return pd.Series(dtype=float)

        final_scores = pd.concat(all_results).sort_index()
        return final_scores

    @classmethod
    def from_meta(cls, meta_path: Union[str, Path]):
        """Maintain backward compatibility."""
        return cls(meta_path)

class SubsetDatasetWrapper:
    """
    Wraps a Qlib DatasetH to force filtering by a specific instrument 
    when prepare() is called.
    """
    def __init__(self, dataset, symbol):
        self.dataset = dataset
        self.symbol = symbol

    def prepare(self, *args, **kwargs):
        # We prepare the full data and then filter it. 
        # This is safer than passing instruments to prepare() as some handlers don't support it in fetch().
        df = self.dataset.prepare(*args, **kwargs)
        if isinstance(df.index, pd.MultiIndex):
            # Index is typically (datetime, instrument)
            # Level 1 is instrument
            return df[df.index.get_level_values(1) == self.symbol]
        return df

    def __getattr__(self, name):
        # Delegate everything else to the original dataset
        return getattr(self.dataset, name)

