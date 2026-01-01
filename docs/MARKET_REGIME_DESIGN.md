# Market Regime Detection Design

## 1. 核心原理 (Core Principles)

Market Regime Detection（市场状态识别）的核心思想是将连贯的市场时间序列切分为离散的“状态（Regimes）”。每个状态代表一种独特的市场微观结构和统计特性（如均值、方差、自相关性）。

在加密货币市场，我们通常定义三种核心状态：

1.  **Bull (牛市 / 上升趋势)**
    *   **特征**: 价格位于均线之上，高点不断垫高，波动率适中。
    *   **策略**: Risk-On。放大 Long 仓位权重，减少 Short，允许适度杠杆。
2.  **Bear (熊市 / 下降趋势)**
    *   **特征**: 价格位于均线之下，低点不断刷新，波动率通常剧烈放大（恐慌抛售）。
    *   **策略**: Risk-Off。清空 Long 仓位（现金为王），或者由 Alpha 模型主导只做 Short。
3.  **Sideways (震荡 / 盘整)**
    *   **特征**: 价格围绕均线反复穿越，无明显方向，RSI 指标在中位数波动。
    *   **策略**: Market Neutral。严格的多空对冲，赚取 Alpha（选币收益），必须对冲掉 Beta（大盘风险）。

## 2. 检测方法 (Detection Methodology)

我们将采用一种**混合统计指标法 (Hybrid Statistical Indicator Approach)**。这种方法比 HMM（隐马尔可夫模型）更可解释，且对噪声更鲁棒。

基准指数：使用 **BTC/USDT** 代表大盘状态。

### 指标组合 (KPIs)

1.  **Trend (趋势项)**: 
    *   使用 **EMA (Exponential Moving Average)** 判断短期和长期趋势。
    *   规则：`Price > EMA_20 > EMA_60` 通常为强势多头。

2.  **Volatility (波动项)**:
    *   使用 **ATR (Average True Range)** 或 **Bollinger Band Width**。
    *   极高的波动率往往伴随着熊市的恐慌底或牛市的泡沫顶。

3.  **Momentum (动量项)**:
    *   使用 **RSI (Relative Strength Index)**。
    *   RSI > 50 偏强，RSI < 50 偏弱。

### 判定逻辑 (Decision Logic)

我们将计算一个 **Market Score (-1.0 to 1.0)**：

*   **+1.0 (Strong Bull)**: BTC > EMA_60 AND RSI > 60
*   **+0.5 (Weak Bull)**: EMA crossover bullish BUT Volatility High
*   **0.0 (Sideways)**: Price oscillating around EMA OR Low Volatility squeezing
*   **-0.5 (Weak Bear)**: BTC < EMA_60 
*   **-1.0 (Strong Bear)**: BTC < EMA_60 AND High Volatility (Panic Selling)

## 3. 实现方案 (Implementation Plan)

### A. 新增模块 `src/regime`

*   `detector.py`: 核心类 `MarketRegimeDetector`。
    *   输入：BTC 的 OHLC 数据。
    *   输出：每日 Regime 标签 (Bull/Bear/Sideways) 和 Risk Scale Factor (0.0 - 1.0)。

### B. 策略集成

修改 `CryptoLongShortStrategy`:
*   在 `__init__` 中接收 `regime_detector`。
*   在 `step` (生成信号前)：
    1.  获取当日/当周的 Market Regime。
    2.  根据 Regime 动态调整 `topk` 和 `risk_degree`。
    
    *   **Example**:
        ```python
        if regime == "BEAR":
            # 强制 SHORT
            direction = "short"
            # 如果模型预测全是正分（不够自信），强制使用 Z-Score Normalization
            # 选取相对最差的标的进行做空 (Fallback Logic)
            
        elif regime == "SIDEWAYS":
            direction = "long-short" # 此刻必须对冲
            # 使用 Z-Score Cross-Sectional Normalization 确保多空平衡
            
        elif regime == "BULL":
            direction = "long" # 允许单边做多
            risk_degree = 0.95
        ```

### C. 信号增强 (Score Enhancement)

为了确保 Long-Short 策略在各种 Regimes 下的鲁棒性，特别是解决 "Bear Regime 下模型输出仍为正值导致无法做空" 的问题，我们引入：

1.  **Z-Score Normalization (横截面归一化)**:
    *   在每个时间戳，对所有标的的预测分数做标准化：`z = (score - mean) / std`。
    *   **作用**: 强制重新分布分数，确保总有相对正（Long）和相对负（Short）的标的，消除全局偏置。

2.  **Strict Short Logic (空头严格筛选)**:
    *   当 Regime 指示必须做空（Bear）时，在 Z-Score 归一化后，仅选取 **负分 (Negative Score)** 且 **绝对值超过阈值** 的标的。
    *   **Stand Aside**: 如果所有标的即便归一化后仍未达到做空阈值（说明下跌信号微弱），则**空仓观望**，不强制开单。
    *   尊重 `signal_threshold`，避免为了做空而做空（Over-trading）。

## 4. 预期效果

通过这个过滤器，我们期望在 **2024 Q3 (Bear/Chop)** 期间：
1.  识别出 BTC 跌破长期均线。
2.  Detector 发出 "Defensive" 信号。
3.  策略自动停止开 Long 仓，或者大幅降低仓位。
4.  **结果**：大幅减少回撤（Drawdown），保住 Q1/Q4 的利润。
