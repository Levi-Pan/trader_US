# 下一周美股财报日历

每周一从 Alpha Vantage 获取预期财报日历，筛选下一个自然周并输出 CSV。

## 使用

首次使用时复制配置模板：

```powershell
Copy-Item .\standard_module\config.example.py .\standard_module\config.py
```

然后在本地 `standard_module/config.py` 中填写自己的 Alpha Vantage API Key。
真实配置文件已被 Git 忽略，不会提交；股票池、请求超时、接口地址和输出目录也在该文件维护。

周一运行：

```powershell
python .\Earning_Calendar.py
```

非周一手工运行：

```powershell
python .\Earning_Calendar.py --allow-any-day
```

指定运行日期补跑：

```powershell
python .\Earning_Calendar.py --run-date 2026-08-10
```

## 字段说明

- `status=ESTIMATED`：Alpha Vantage 提供的预期日期，并非公司 IR 正式确认。
- `session=UNKNOWN`：该接口没有可靠的盘前/盘后时间。
- `config.json` 和输出目录均被 Git 忽略。

## FMP历史回测数据

FMP下载程序使用当前的 Stable API，生成回测要求的四份标准CSV。首次使用时，
在本地 `standard_module/config.py` 中填写：

```python
FMP_API_KEY = "你的FMP_API_KEY"
```

先用少量股票验证接口权限：

```powershell
python .\app\fmp_data_run.py `
  --symbols "AAPL,MSFT,NVDA,AMZN,META" `
  --from 2021-01-01 `
  --to 2025-12-31 `
  --output-dir "D:\Code All\trader_US\output\fmp"
```

也可以通过环境变量提供密钥，避免在任何文件中保存：

```powershell
$env:FMP_API_KEY="你的FMP_API_KEY"
```

下载完成后运行回测：

```powershell
python .\backtest.py `
  --prices "D:\Code All\trader_US\output\fmp\prices.csv" `
  --fundamentals "D:\Code All\trader_US\output\fmp\fundamentals.csv" `
  --calendar "D:\Code All\trader_US\output\fmp\earnings_calendar.csv" `
  --results "D:\Code All\trader_US\output\fmp\earnings_results.csv" `
  --output-dir "D:\Code All\trader_US\output\backtest"
```

输出目录中的 `dataset_manifest.json` 记录数据日期、股票池、行数和时点假设。
FMP历史财报日历没有完整的日期修订轨迹，程序默认假设财报日期提前30个自然日
已知；缺少公布时段时默认按AMC处理。这属于研究近似，不是严格的
Point-in-Time数据，不能直接据此评价实盘收益。
