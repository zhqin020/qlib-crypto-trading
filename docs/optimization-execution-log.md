# Adaptive Sigma Threshold Optimization - 执行记录

**开始时间**: 2026-01-02 23:25  
**状态**: 运行中 🔄

---

## 🎯 优化目标

找到最优的 `min_sigma_threshold` 参数，使得：
- **Sharpe Ratio** > 1.0
- **Win Rate** > 50%
- **Max Drawdown** < 15%

---

## 📋 测试配置

- **模型**: `models/per_symbol_models_20260102_020624.json`
- **数据集**: `crypto_1h_future`
- **回测期间**: 2024-05-03 至 2025-01-01
- **测试参数**:
  - `min_sigma`: [0.0, 0.5, 0.75, 1.0, 1.25, 1.5]
  - `topk`: [3]
  - **总组合数**: 6

---

## 📊 预期结果（基于信号分析）

| min_sigma | 预期合格信号 | 预期置信度 | 预期交易减少 |
|-----------|------------|-----------|------------|
| 0.0σ      | 100%       | ~60%      | 0%         |
| 0.5σ      | 25%        | 74%       | 75%        |
| 0.75σ     | 12%        | 88%       | 88%        |
| 1.0σ      | 9%         | 94%       | 91%        |
| 1.25σ     | 8%         | 96%       | 92%        |
| 1.5σ      | 7%         | 98%       | 93%        |

---

## ⏱️ 预计耗时

- 每个回测约 1-2 分钟
- 总计约 **6-12 分钟**

---

## 📁 输出文件

1. **优化结果**: `analytics/sigma_optimization_results.csv`
2. **运行日志**: `analytics/optimization_log.txt`
3. **回测详情**: `backtests/per_symbol_models_*_backtest.json`

---

## 🔍 监控命令

```bash
# 查看实时进度
tail -f analytics/optimization_log.txt

# 查看最新日志
tail -n 50 logs/qlib-crypto-1.log

# 检查是否完成
ls -lh analytics/sigma_optimization_results.csv
```

---

## 📝 下一步

优化完成后：
1. 查看 `analytics/sigma_optimization_results.csv` 中的结果
2. 选择最优参数配置
3. 更新 `config/trading_params.json`
4. 运行最终验证回测
5. 部署到生产环境

---

**更新时间**: 2026-01-02 23:26
