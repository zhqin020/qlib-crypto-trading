# 🧠 Technical Design: Instrument Embedding for Global Models

## 🎯 Objective
To allow a single **Global Model** (e.g., ALSTM, LightGBM) to learn and distinguish between the behaviors of different assets (e.g., BTC vs. PEPE) without splitting the dataset into multiple small models.

## ⚖️ Pipeline Comparison: Before vs. After

Here is a detailed breakdown of how the pipeline changes from the **Original Global Model** to the **New Symbol Embedding Model**.

| Pipeline Stage | 1. Original Global Model (Current) | 2. New Symbol Embedding Model (Proposed) |
| :--- | :--- | :--- |
| **1. Feature Extraction** | Calculates **158** Alpha Factors (Alpha158). <br> *Purely numerical market data (Price, Vol, Momentum).* | Calculates **158** Factors + **1 Instrument ID**. <br> *Market data + Identity data.* |
| **2. Data Preprocessing** | Normalizes (Z-Score) all 158 features. | Normalizes 158 features. **Leaves Feature 159 (ID) raw/integer.** |
| **3. Input Tensor** | Shape: `[Batch, Seq_Len, 158]` <br> Dtype: `float32` | Shape: `[Batch, Seq_Len, 159]` <br> Dtype: `float32` (ID is cast to float for storage, cast back to int in model) |
| **4. Neural Net Logic** | **Input**: 158 Features <br> **Process**: `RNN(Features) -> Hidden_State` <br> *Model treats BTC and PEPE identically if their charts look the same.* | **Input**: 158 Feat + 1 ID <br> **Process**: `RNN(Features)` **+** `Embedding(ID)` <br> **Fusion**: `Concat(Hidden_State, Asset_Vector)` <br> *Model knows "This is BTC" and applies trend logic; "This is PEPE" and applies reversion logic.* |
| **5. Tree Model Logic** | **LightGBM**: Splits trees based on values (e.g., `feature_12 > 0.5`). <br> *Cannot explicitly group assets.* | **LightGBM**: Splits based on values **AND** ID (e.g., `if ID == BTC_ID then...`). <br> *Uses `categorical_feature` to learn asset-specific sub-trees.* |
| **6. Inference (Live)** | Feed real-time 158 factors. | Feed real-time 158 factors + **Hash(Symbol_Name)**. |

---

## 🛠 Step 1: Data Engineering (The "Hashing Trick")

To avoid maintaining a fragile `symbol_to_id.json` mapping file, we use **Feature Hashing**.

-   **Concept**: Deterministically map the symbol string to an integer.
    ```python
    # Logic in Data Handler
    instrument_id = zlib.adler32(symbol.encode()) % 100
    ```
-   **Implementation**:
    -   Set `NUM_EMBEDDINGS = 100` (Sufficient for ~50 crypto assets).
    -   In the Data Loader: Append this `id` as the **159th feature**.
-   **Stateless**: Works instantly for new symbols (e.g., `SUI/USDT` gets an ID automatically).

## 🏗 Step 2: Model Architecture Strategies

### A. Neural Networks (LSTM, ALSTM, Transformer)
**Method**: Learnable Embedding Vector.
1.  **Split**:
    -   `x_feat = input[:, :, :-1]` (The 158 Factors)
    -   `x_id = input[:, 0, -1]` (The Instrument ID)
2.  **Forward Pass**:
    ```python
    # 1. Get Asset "Personality" Vector
    emb_vector = self.embedding(x_id) # Shape: (Batch, 16)
    
    # 2. Extract Market State
    rnn_out = self.rnn(x_feat)        # Shape: (Batch, Hidden)
    
    # 3. Fuse Information
    fused = torch.cat([rnn_out, emb_vector], dim=1)
    
    # 4. Predict
    return self.fc(fused)
    ```

### B. Gradient Boosting (LightGBM, XGBoost)
**Method**: Native Categorical Features.
1.  **LightGBM**:
    -   Pass the column index of the injected ID to `categorical_feature`.
    -   `lgb.train(..., categorical_feature=[158])`
    -   GBDT will automatically learn: *If ID is in {Group_A}, use Momentum; If ID is in {Group_B}, use Mean Reversion.*

## 🚀 Benefits
1.  **Unified Pipeline**: No need to train 10 different models for 10 coins.
2.  **Transfer Learning**: If "SUI" behaves like "APT" (similar hashes or learned behavior), the model adapts quickly.
3.  **Regime Awareness**: The model can learn that "ID #42 (BTC)" leads the market, while "ID #12 (ETH)" follows.

## 📅 Execution Plan
1.  **Patch Data Pipeline**: Modify `src/data_pipeline` to generate the 159-dim dataset.
2.  **Update Config**: Add `categorical_feature` support for LightGBM in `trading_params.json`.
3.  **Refactor Models**: Update `ALSTM` to handle the `(Fusion)` logic.
