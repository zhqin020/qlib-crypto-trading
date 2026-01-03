# Per-Symbol Modeling 完整流程总结

**日期**: 2026-01-02  
**状态**: 基线建立完成，进入优化阶段

---

## 🎯 已完成的工作流程

### 1. 数据准备 ✅
```bash
# 下载最新数据（5个主要币种）
conda run -n qlib python scripts/download_sample_data.py \
  --symbols "BTC,ETH,SOL,AVAX,DOT" --interval 1h

# 转换为 Qlib 格式
conda run -n qlib python scripts/convert_to_qlib.py \
  --freq 1h --market-type future
```

**结果**：
- 数据集：`data/qlib/crypto_1h_future/`
- 币种：BTC, ETH, SOL, AVAX, DOT (+ BNB, ADA, LINK, LTC, XRP, SUI)
- 时间范围：2020-01-01 至 2026-01-01

---

### 2. 模型训练 ✅
```bash
# 为每个币种训练独立的 ALSTM 模型
conda run -n qlib python scripts/train_per_symbol.py \
  --symbols "BTC,ETH,SOL,AVAX,DOT" --device cpu
```

**输出**：
- 模型映射文件：`models/per_symbol_models_20260102_020624.json`
- 单个模型文件：`models/trained/alstm_<symbol>_<timestamp>.pkl`
- 训练参数：
  - d_feat: 158 (Alpha158 特征集)
  - hidden_size: 32
  - num_layers: 2
  - dropout: 0.443
  - epochs: 100
  - batch_size: 512

---

### 3. 回测验证 ✅
```bash
# 使用 Per-Symbol 模型进行回测
conda run -n qlib python scripts/run_backtest.py \
  models/per_symbol_models_20260102_020624.json \
  --dataset crypto_1h_future \
  --start 2024-05-03 --end 2025-01-01 \
  --long-short --topk 3 --direction long-short
```

**基线结果**（固定 TopK=3）：
```json
{
  "annualized_return": 0.0174 (1.74%),
  "sharpe_ratio": 0.231,
  "sortino_ratio": 0.240,
  "max_drawdown": 0.239 (23.9%),
  "calmar_ratio": 0.073,
  "win_rate": 0.294 (29.4%),
  "total_trades": 5833
}
```

**问题诊断**：
- Sharpe Ratio 远低于目标 (0.23 vs 1.0)
- Win Rate 过低 (29.4% vs 45%+)
- 交易过于频繁（每小时交易）
- 大部分信号置信度不足

---

### 4. 信号质量分析 ✅
```bash
# 分析历史信号的 Sigma 分布
conda run -n qlib python scripts/analyze_signal_quality.py
```

**关键发现**：
| Sigma 范围 | 信号数量 | 占比   | 平均置信度 |
|-----------|---------|--------|-----------|
| < 0.5σ    | 22,054  | 76.0%  | ~53%      |
| 0.5-1.0σ  | 4,403   | 15.2%  | 73.6%     |
| 1.0-1.5σ  | 702     | 2.4%   | 93.8%     |
| 1.5-2.0σ  | 454     | 1.6%   | 96.4%     |
| > 2.0σ    | 1,423   | 4.9%   | 99.6%     |

**建议阈值**：
- **保守策略**: 1.5σ (置信度 98%, 交易减少 93.5%)
- **平衡策略**: 1.0σ (置信度 94%, 交易减少 91%)
- **激进策略**: 0.75σ (置信度 88%, 交易减少 88%)

---

## 📁 核心文件结构

```
qlib-crypto/
├── models/
│   ├── per_symbol_models_20260102_020624.json  # 模型映射
│   └── trained/
│       ├── alstm_BTC_*.pkl
│       ├── alstm_ETH_*.pkl
│       └── ...
├── backtests/
│   └── per_symbol_models_20260102_020624_backtest.json  # 回测结果
├── analytics/
│   ├── sigma_distribution_analysis.png  # 信号分布图
│   └── signal_quality_data.csv  # 原始数据
├── scripts/
│   ├── train_per_symbol.py  # 批量训练脚本
│   ├── analyze_signal_quality.py  # 信号分析脚本
│   └── run_backtest.py  # 回测脚本
├── src/
│   ├── models/
│   │   └── wrappers.py  # MultiModelWrapper (多模型调度)
│   ├── backtesting/
│   │   ├── strategies.py  # CryptoLongShortStrategy (含 Sigma 计算)
│   │   └── engine.py  # 回测引擎 (支持 JSON 模型映射)
│   └── serving/
│       └── predictor.py  # QlibPredictor (Per-Symbol 推理)
└── issues/
    ├── 003-per-symbol-modeling.md  # CLOSED
    └── 004-adaptive-sigma-threshold.md  # OPEN (下一步)
```

---

## 🚀 下一步：方向 1 - 自适应 Sigma 阈值优化

### 目标
将固定 TopK 策略升级为**置信度驱动的自适应执行**：
- 只交易高置信度信号 (Sigma ≥ 阈值)
- 通过网格搜索找到最优 `min_sigma` 参数
- 目标：Sharpe > 1.0, Win Rate > 50%

### 实施步骤

#### Step 1: 修改策略类
在 `src/backtesting/strategies.py` 中添加 `min_sigma_threshold` 参数：

```python
def __init__(self, ..., min_sigma_threshold=0.0, **kwargs):
    self.min_sigma_threshold = min_sigma_threshold
    ...

def generate_target_weight_position(self, ...):
    ...
    # 过滤低置信度信号
    if self.min_sigma_threshold > 0:
        qualified = {
            inst: score[inst] 
            for inst, sigma in sigmas.items() 
            if abs(sigma) >= self.min_sigma_threshold
        }
        if not qualified:
            logger.info(f"No signals meet {self.min_sigma_threshold}σ threshold")
            return {}
        score = pd.Series(qualified)
    ...
```

#### Step 2: 参数网格搜索
创建 `scripts/optimize_sigma_threshold.py`：

```python
# 测试不同的 min_sigma 值
thresholds = [0.5, 0.75, 1.0, 1.25, 1.5]
topk_values = [2, 3, 5]

for min_sigma in thresholds:
    for topk in topk_values:
        # 运行回测
        result = run_backtest(
            model_id="models/per_symbol_models_20260102_020624.json",
            min_sigma_threshold=min_sigma,
            topk=topk,
            ...
        )
        # 记录结果
        results.append({
            'min_sigma': min_sigma,
            'topk': topk,
            'sharpe': result['sharpe_ratio'],
            'win_rate': result['win_rate'],
            ...
        })
```

#### Step 3: 选择最优参数
根据网格搜索结果，选择满足以下条件的参数组合：
- Sharpe Ratio > 1.0
- Win Rate > 50%
- Max Drawdown < 15%

#### Step 4: 更新配置并验证
```bash
# 使用最优参数重新回测
conda run -n qlib python scripts/run_backtest.py \
  models/per_symbol_models_20260102_020624.json \
  --dataset crypto_1h_future \
  --start 2024-05-03 --end 2025-01-01 \
  --long-short --topk 3 --direction long-short \
  --min-sigma 1.0  # 假设最优值
```

---

## 📊 预期改进

基于信号分析，预期使用 **1.0σ 阈值**后：

| 指标                | 当前值  | 预期值    | 改进幅度 |
|--------------------|---------|----------|---------|
| Sharpe Ratio       | 0.23    | 1.0-1.5  | +335%   |
| Win Rate           | 29.4%   | 50-60%   | +70%    |
| Max Drawdown       | 23.9%   | 12-15%   | -37%    |
| Total Trades       | 5,833   | ~520     | -91%    |
| Avg Trade Quality  | 低      | 高       | +++     |

---

## 🔧 技术亮点

1. **MultiModelWrapper**: 无缝集成多个单币种模型到 Qlib 回测框架
2. **Sigma 置信度**: 基于历史预测分布的统计显著性量化
3. **数据驱动优化**: 避免"拍脑袋"，用实际数据指导参数选择
4. **模块化设计**: 训练、推理、回测、分析各环节独立可复用

---

## 📝 备注

- 当前使用 CPU 训练，GPU 可显著加速
- 可考虑扩展到更多币种（当前仅 5 个）
- 未来可引入动态阈值（根据市场状态调整）
- 考虑添加 MC Dropout 获取模型内生不确定性
