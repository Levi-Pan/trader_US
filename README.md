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
