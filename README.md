# 美股财报研究项目

当前模块每周一从 Alpha Vantage 获取下一周预期财报日历，再用 yfinance 补充公司所属板块并输出 CSV。后续回测、指标和策略代码可以在独立业务目录中继续扩展。

## 目录

```text
trader_US/
├── app/                         # 可直接运行的任务入口
├── data_sources/                # Alpha Vantage、Yahoo Finance 数据源
├── earnings_calendar/           # 财报日历业务逻辑与 CSV 输出
├── private_module/              # 项目日志等私有公共模块
├── standard_module/             # 可复用统一配置
├── output/                      # CSV 与板块缓存，不提交 Git
├── logs/                        # 每日运行日志，不提交 Git
├── requirements.txt
└── test_calendar_service.py
```

## 使用

首次使用时复制配置模板：

```powershell
Copy-Item .\standard_module\config.example.py .\standard_module\config.py
```

然后在本地 `standard_module/config.py` 中填写自己的 Alpha Vantage API Key。
真实配置文件已被 Git 忽略，不会提交；股票池、请求超时、接口地址和输出目录也在该文件维护。

安装依赖：

```powershell
python -m pip install -r .\requirements.txt
```

周一运行：

```powershell
python .\app\earning_calendar_run.py
```

非周一手工运行：

```powershell
python .\app\earning_calendar_run.py --allow-any-day
```

指定运行日期补跑：

```powershell
python .\app\earning_calendar_run.py --run-date 2026-08-10
```

Windows 任务计划程序可设置为北京时间每周一 08:30：程序填 `python`，参数填
`D:\LeviPan\trader_US\app\earning_calendar_run.py`，起始位置填 `D:\LeviPan\trader_US`。

## 字段说明

- `status=ESTIMATED`：Alpha Vantage 提供的预期日期，并非公司 IR 正式确认。
- `session=UNKNOWN`：该接口没有可靠的盘前/盘后时间。
- `所属板块` 来自 yfinance `Ticker.get_info()` 的 `sector` 字段，Yahoo 缺失或请求失败时为 `UNKNOWN`。
- 板块和行业信息保存在 `output/company_profiles.sqlite3`，默认缓存 30 天，减少重复请求。
- yfinance 使用 Yahoo 的公开接口，可能出现限流或字段缺失，不应作为交易关键链路的唯一数据源。
- 输出目录和真实配置均被 Git 忽略。
- 日志同时输出到控制台和 `logs/earning_calendar_YYYYMMDD.log`，同一天重复运行会追加记录。

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
