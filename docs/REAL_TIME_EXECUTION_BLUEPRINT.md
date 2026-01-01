# Real-time Order Execution Blueprint

This document outlines the architecture, technology stack, and implementation roadmap for transitioning from historical backtesting to live trading on the Qlib-Crypto platform.

## 🏗️ System Architecture

The real-time execution system will be composed of three decoupled modules:

### 1. Data Pipeline (Real-time Sync)
*   **Role**: Synchronize the local Qlib binary dataset with the latest exchange market data.
*   **Workflow**:
    1.  Fetch the latest closed 1h OHLCV via **CCXT**.
    2.  Append data to local CSV storage.
    3.  Trigger Qlib's `dump_bin` to update the binary data path.
    4.  Ensure dataset consistency for the predictor.

### 2. Signal Generator (Predictor)
*   **Role**: Generate trading weights for the current market state.
*   **Workflow**:
    1.  Load the latest trained model (`best_params`).
    2.  Generate scores for the target universe.
    3.  Apply `signal_threshold` and `topk` constraints.
    4.  Output **Target Weights** (e.g., BTC: +0.25, ETH: -0.1).

### 3. Local Paper Executor (Hybrid Simulation)
*   **Role**: Simulate detailed order execution and position tracking locally to bypass Demo exchange liquidity issues.
*   **Workflow**:
    1.  **Sync**: Fetch current *real* market prices via CCXT (for accurate mark-to-market).
    2.  **Calculate**: Compare new target weights vs. locally stored positions in PostgreSQL.
    3.  **Simulate Trade**:
        *   Assume "Fill at Current Price" (with configurable slippage model).
        *   Calculate Transaction Fees (e.g., Maker/Taker rates).
    4.  **Persist**: Update `positions` and `orders` tables in PostgreSQL.
    5.  **Report**: Generate PnL reports based on high-fidelity simulation.

---

## 🛠️ Technology Stack

*   **Connectivity**: [CCXT](https://github.com/ccxt/ccxt) (Standardized exchange interface).
*   **Scheduling**: `APScheduler` (Cron-like precision for hourly rebalancing).
*   **Persistence**: PostgreSQL (Tracking orders, trades, and equity curve).
*   **Configuration**: Integrated into `config/trading_params.json` under a new `live` section.

---

## 🗄️ Database Schema Design (PostgreSQL)

To support local simulation, we need robust tables for tracking the virtual portfolio:

### 1. `simulation_accounts`
*   `id`: UUID
*   `name`: "OKX Paper", "Binance Shadow"
*   `balance`: Available Cash (USDT)
*   `equity`: Total Equity
*   `updated_at`: Timestamp

### 2. `positions`
*   `account_id`: FK
*   `symbol`: "BTC/USDT"
*   `amount`: Signed float (Position Size)
*   `entry_price`: Avg Entry Price
*   `current_price`: Last synced price
*   `unrealized_pnl`: Float

### 3. `orders`
*   `id`: UUID
*   `account_id`: FK
*   `symbol`: "BTC/USDT"
*   `side`: BUY/SELL
*   `type`: MARKET/LIMIT
*   `amount`: Float
*   `price`: Fill Price
*   `fee`: Transaction Fee
*   `status`: FILLED/CANCELED
*   `created_at`: Timestamp

---

## 🚀 Strategic Roadmap

### Phase 1: Paper Trading (Shadow Mode)
*   Run the full pipeline with live data.
*   Execute "Virtual Orders" only.
*   Compare virtual performance with backtest expectations.
*   **Goal**: Zero-risk validation of data sync and signal timing.

### Phase 2: Single-Pair Live (Micro-Cap Trading)
*   Connect API keys with restricted permissions.
*   Trade a single instrument (e.g., BTC/USDT) with minimal capital.
*   Validate Stop-Loss/Take-Profit and emergency exit logic.
*   **Goal**: Ensure API stability and basic execution safety.

### Phase 3: Portfolio Live (Full Deployment)
*   Deployment of the full Long-Short portfolio strategy.
*   Multi-asset rebalancing.
*   Implementation of advanced execution algorithms (TWAP) to minimize slippage.
*   **Goal**: Stable, automated alpha generation.

---

## ⚠️ Key Challenges & Mitigations

| Challenge | Mitigation Strategy |
| :--- | :--- |
| **Data Lag** | Buffer prediction by 60 seconds after hour-close to ensure candle finality. |
| **Execution Slippage** | Use `signal_threshold` to trade only high-conviction signals; implement limit orders once capital grows. |
| **API Connectivity** | Implement robust retry logic with exponential backoff via CCXT. |
| **Risk Control** | Implement a "Circuit Breaker" that stops all trading if drawdown exceeds X% in 24h. |
