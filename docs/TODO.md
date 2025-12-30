我们执行以下步骤：

复制配置：将 
config/trading_params.json
 复制为 config/btc_eth_params.json。
修改新配置：在 config/btc_eth_params.json 中，将 symbols 修改为仅含 BTC 和 ETH。
支持指定配置：我们需要稍微修改一下 
scripts/train_sample_model.py
 和 
scripts/run_backtest.py
，让它们能接受一个 --config 参数（或者自动识别）。目前它们是硬编码读取 
config/trading_params.json
 的。
为了不改动太多代码逻辑（增加复杂性），我建议采用一个临时环境变量或者简单地在脚本里增加对配置文件的参数支持。

查看 
scripts/train_sample_model.py
，如果不加参数支持，我们可能需要用更黑客的方法。

最佳方案： 我将为您修改 
scripts/train_sample_model.py
 和 
scripts/run_backtest.py
，让它们支持一个可选的 --config 参数。这本身就是一个很好的功能增强。

1. 复制配置文件
我先创建 config/btc_eth_params.json 并修改其内容。

2. 修改新配置文件只包含 BTC/ETH
我将读取 
config/btc_eth_params.json
 并把 symbols 列表截断。