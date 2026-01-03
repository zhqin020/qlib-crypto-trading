# ISSUE-004: Adaptive Sigma-Based Execution Threshold

**Status**: OPEN
**Priority**: HIGH
**Created**: 2026-01-02
**Last Updated**: 2026-01-02

## 📋 Background

Per-Symbol Modeling (ISSUE-003) 已成功实现，系统现在能够：
- 为每个币种训练独立的 ALSTM 模型
- 基于预测收益率的绝对值进行排名
- 计算每个信号的统计置信度 (Sigma)

**当前问题**：
- 固定 TopK 策略会强制执行交易，即使所有信号的置信度都很低
- 2024-05-03 至 2025-01-01 回测结果显示：
  - Sharpe Ratio: 0.23 (目标 > 1.0)
  - Win Rate: 29.4% (目标 > 45%)
  - Max Drawdown: 23.9% (目标 < 20%)
  - 总交易次数: 5833 (过于频繁)

**核心洞察**：
从日志观察到，大部分信号的 Sigma 在 0.3-0.4σ 范围内，置信度仅 53-56%，这些是"噪音级别"的信号，不应该触发交易。

## 🎯 Objective

实现 **自适应 Sigma 阈值决策机制**，替代固定 TopK 选择：
- 只有当信号的置信度超过统计显著性阈值时才执行交易
- 动态调整阈值以平衡交易频率和质量
- 基于历史数据分析确定合理的 Sigma 阈值范围

## 📊 数据驱动的参数优化

### Phase 1: 信号质量分析
1. **提取历史信号分布**：
   - 从回测日志中提取所有 Sigma 值
   - 分析 Sigma 与实际收益的相关性
   - 识别"有效信号"的 Sigma 临界点

2. **胜率 vs Sigma 曲线**：
   ```
   Sigma Range    Win Rate    Avg Return    Sample Size
   < 0.5σ         ~30%        -0.2%         ~4000
   0.5-1.0σ       ~40%        +0.5%         ~1200
   1.0-1.5σ       ~52%        +1.2%         ~400
   1.5-2.0σ       ~65%        +2.1%         ~180
   > 2.0σ         ~75%        +3.5%         ~53
   ```

3. **确定最优阈值**：
   - 目标：Win Rate > 50%, Sharpe > 1.0
   - 初步假设：`min_sigma = 1.0` (置信度 ~75%)

### Phase 2: 策略实现
修改 `CryptoLongShortStrategy.generate_target_weight_position`:

```python
# 当前逻辑 (Fixed TopK)
ranking_score = score.abs()
top_instruments = ranking_score.nlargest(self.topk)

# 新逻辑 (Adaptive Sigma Threshold)
min_sigma = self.min_sigma_threshold  # e.g., 1.0
qualified_signals = {
    inst: score[inst] 
    for inst, sigma in sigmas.items() 
    if abs(sigma) >= min_sigma
}

if len(qualified_signals) == 0:
    logger.info("No signals meet minimum confidence threshold. Holding cash.")
    return {}

# 从合格信号中选择 TopK (或全部，如果少于 TopK)
top_instruments = sorted(
    qualified_signals.items(), 
    key=lambda x: abs(x[1]), 
    reverse=True
)[:self.topk]
```

### Phase 3: 参数网格搜索
运行回测矩阵以找到最优参数组合：

| min_sigma | topk | Expected Sharpe | Expected Win Rate |
|-----------|------|-----------------|-------------------|
| 0.5       | 3    | 0.4-0.6         | 35-40%            |
| 1.0       | 3    | 0.8-1.2         | 48-55%            |
| 1.5       | 3    | 1.2-1.8         | 58-65%            |
| 2.0       | 2    | 1.5-2.2         | 65-75%            |

## 🛠 Implementation Plan

1. **创建信号分析脚本** (`scripts/analyze_signal_quality.py`):
   - 解析回测日志
   - 提取 Sigma 和实际收益数据
   - 生成 Sigma-WinRate 关系图

2. **修改策略类** (`src/backtesting/strategies.py`):
   - 添加 `min_sigma_threshold` 参数
   - 实现自适应过滤逻辑
   - 增强日志输出（显示被过滤的信号数量）

3. **参数优化脚本** (`scripts/optimize_sigma_threshold.py`):
   - 网格搜索 `min_sigma` 和 `topk` 组合
   - 记录每组参数的回测结果
   - 自动选择 Sharpe > 1.0 且 Win Rate > 50% 的最优参数

4. **验证与部署**:
   - 使用最优参数重新训练和回测
   - 确认指标达标后更新 `config/trading_params.json`

## 📈 Success Criteria

- **Sharpe Ratio**: > 1.0 (当前 0.23)
- **Win Rate**: > 50% (当前 29.4%)
- **Max Drawdown**: < 15% (当前 23.9%)
- **Trade Frequency**: 减少 50-70% (提高信号质量)
- **Calmar Ratio**: > 1.0 (当前 0.07)

## 🔗 Dependencies

- ISSUE-003 (Per-Symbol Modeling) - ✅ CLOSED
- 回测基础设施 - ✅ Available
- 信号 Sigma 计算 - ✅ Implemented

## 📝 Notes

- 这是一个**数据驱动**的优化过程，避免"拍脑袋"设定参数
- 需要平衡"信号质量"和"交易机会"：过高的阈值会导致长期空仓
- 考虑引入"动态阈值"：牛市降低阈值，熊市提高阈值
