# 财报日历下载

核心函数：`data_sources/alpha_vantage.py` 中的 `fetch_earning_calendar()`。
从 Alpha Vantage 获取未来财报日历，返回原始记录列表。

直接运行下面入口，自动输出下一自然周的全市场财报记录，无需启动参数：

```powershell
python "D:\Code All\trader_US\app\earning_calendar_run.py"
```

也可以在 VS Code 打开入口文件直接点击运行。
CSV 保存到 `output/earnings_开始日期_结束日期.csv`，采用 UTF-8 BOM 编码，可用 Excel 打开。
保留接口原始字段，如股票代码、公司名称、财报日期、EPS预测及币种。

Alpha Vantage API Key 继续使用 `standard_module/config.py` 中已有配置。
首次配置可复制 `standard_module/config.example.py` 为 `config.py` 并设置密钥。
仅使用 Python 标准库，不需要长桥、Yahoo、股票池、选股策略或人工财报文件。
接口提供的是预期财报日期。
