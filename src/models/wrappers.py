
import pickle
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, Union

from qlib.data.dataset import DatasetH

logger = logging.getLogger("MultiModelWrapper")

class MultiModelWrapper:
    """
    A Qlib-compatible model wrapper that dispatches predictions to per-symbol models.
    """
    def __init__(self, model_mapping_path: Union[str, Path]):
        self.mapping_path = Path(model_mapping_path)
        self.models: Dict[str, Any] = {}
        self.global_model = None
        self._load_models()

    def _load_models(self):
        if not self.mapping_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {self.mapping_path}")
        
        import json
        with open(self.mapping_path, "r") as f:
            data = json.load(f)
        
        symbol_map = data.get("symbols", {})
        for symbol, info in symbol_map.items():
            model_path = Path(info.get("model_path"))
            if not model_path.is_absolute():
                # Resolve relative to project root or mapping file
                model_path = self.mapping_path.parent.parent / model_path 
            
            try:
                with open(model_path, "rb") as f:
                    self.models[symbol] = pickle.load(f)
            except Exception as e:
                logger.error(f"Failed to load model for {symbol} at {model_path}: {e}")

        logger.info(f"MultiModelWrapper loaded {len(self.models)} models from {self.mapping_path.name}")

    def predict(self, dataset: DatasetH) -> pd.Series:
        """
        Produce predictions by splitting the dataset into per-instrument subsets.
        """
        # 1. Prepare full data to get index
        df_full = dataset.prepare("test", col_set="feature")
        if df_full.empty:
            return pd.Series(dtype=float)

        # Index is (datetime, instrument)
        symbols_in_data = df_full.index.get_level_values(1).unique().tolist()
        
        all_results = []
        for symbol in symbols_in_data:
            # Case-insensitive lookup
            model = self.models.get(symbol)
            if not model:
                model = self.models.get(symbol.upper())
            if not model:
                model = self.models.get(symbol.lower())
            
            if not model:
                continue
            
            # Wrap dataset for this specific instrument
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

        return pd.concat(all_results).sort_index()

class SubsetDatasetWrapper:
    def __init__(self, dataset, symbol):
        self.dataset = dataset
        self.symbol = symbol

    def prepare(self, *args, **kwargs):
        df = self.dataset.prepare(*args, **kwargs)
        if isinstance(df.index, pd.MultiIndex):
            return df[df.index.get_level_values(1) == self.symbol]
        return df

    def __getattr__(self, name):
        return getattr(self.dataset, name)
