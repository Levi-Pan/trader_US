# 下一周美股财报日历

每周一从 Alpha Vantage 获取预期财报日历，筛选下一个自然周并输出 CSV。

## 使用

统一配置位于 `standard_module/config.py`。股票池、请求超时、接口地址和输出目录都在该文件维护。

API Key 使用环境变量配置，避免提交到 Git：

```powershell
$env:ALPHAVANTAGE_API_KEY = "你的 API Key"
```

周一运行：

```powershell
python .\earnings_calendar.py
```

非周一手工运行：

```powershell
python .\earnings_calendar.py --allow-any-day
```

指定运行日期补跑：

```powershell
python .\earnings_calendar.py --run-date 2026-08-10
```

Windows 任务计划程序可设置为北京时间每周一 08:30：程序填 `python`，参数填
`D:\LeviPan\trader_US\earnings_calendar.py`，起始位置填 `D:\LeviPan\trader_US`。

## 字段说明

- `status=ESTIMATED`：Alpha Vantage 提供的预期日期，并非公司 IR 正式确认。
- `session=UNKNOWN`：该接口没有可靠的盘前/盘后时间。
- `config.json` 和输出目录均被 Git 忽略。
