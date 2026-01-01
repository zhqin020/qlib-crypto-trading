# 实盘模型集成计划 (Live Model Integration Plan)

本文档记录了将训练好的 Qlib 模型集成到自动化交易循环中的详细方案。

## 1. 方案架构

目标是构建一个端到端的自动化链条：
`交易所数据抓取` -> `Qlib Binarize` -> `特征生成 (Alpha158)` -> `模型推理 (Inference)` -> `OMS 执行`

## 2. 核心模块

- **Predictor (预测器)**: 加载导出的 `model.bin`，处理特征对齐，输出排序分数。
- **Live Data Bridge**: 增量抓取 K 线并调用 `dump_bin`，确保本地 Qlib 数据库为最新。
- **Online Features**: 利用 Qlib 的 `D.features` 实时计算当前时刻的特征向量。

## 3. 实施步骤

| 阶段 | 任务 | 目标 | 状态 |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Inference Engine** | 创建 `src/serving/predictor.py`，支持加载 ALSTM/LGBM 并进行推理。 | 🔄 进行中 |
| **Phase 2** | **Data Bridge** | 完善 `LiveTradingLoop` 中的 `dump_bin` 自动化，同步最新价格。 | ⏳ 待处理 |
| **Phase 3** | **Feature Layer** | 实现实时特征提取函数，处理多币种特征对齐。 | ⏳ 待处理 |
| **Phase 4** | **Shadow Test** | 在实盘循环中切换至真实模型，进行影子运行测试。 | ⏳ 待处理 |

## 4. 关键文件

- `src/serving/predictor.py`: 模型封装类。
- `src/serving/live_loop.py`: 调度主逻辑。
- `config/trading_params.json`: 存储模型路径与推断配置。
