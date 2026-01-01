from qlib.data.dataset.processor import Processor

import pandas as pd
import zlib
import numpy as np

class HashInstrumentProcessor(Processor):
    def __init__(self, num_embeddings=100, fields_group="feature"):
        self.num_embeddings = num_embeddings
        self.fields_group = fields_group

    def __call__(self, df):
        # df index is often MultiIndex (datetime, instrument)
        # But processors might receive df with columns as MultiIndex (group, feature)
        # check if index is valid
        if isinstance(df.index, pd.MultiIndex):
            # level 1 is instrument
            idx_names = df.index.names
            inst_level_idx = -1
            for i, name in enumerate(idx_names):
                if name == "instrument":
                    inst_level_idx = i
                    break
            
            if inst_level_idx == -1:
                # Default to level 1 for (date, instrument)
                inst_level_idx = 1
            
            instruments = df.index.get_level_values(inst_level_idx)
        else:
            return df
            
        # Hash logic
        # We need to map instruments (strings) to int ID
        
        # 1. ensure instruments are strings
        inst_str = instruments.astype(str)
        
        # 2. apply hash
        # To make it efficient, we can get unique instruments, hash them, then map back
        uniques = np.unique(inst_str)
        hash_map = {
            inst: zlib.adler32(inst.encode("utf-8")) % self.num_embeddings
            for inst in uniques
        }
        
        # 3. map to create column
        hashed_ids = inst_str.map(hash_map).to_numpy() # use numpy array
        
        # 4. Add to DF
        if isinstance(df.columns, pd.MultiIndex):
             # Qlib handler output usually has MultiIndex columns: (group, name)
            col_name = (self.fields_group, "instrument_id")
        else:
            col_name = "instrument_id"
        
        # Assign
        df[col_name] = hashed_ids
        
        return df
