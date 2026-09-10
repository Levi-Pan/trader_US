# 缇庤偂璐㈡姤鐮旂┒椤圭洰

褰撳墠妯″潡姣忓懆涓€浠?Alpha Vantage 鑾峰彇涓嬩竴鍛ㄩ鏈熻储鎶ユ棩鍘嗭紝鍐嶇敤 yfinance 琛ュ厖鍏徃鎵€灞炴澘鍧楀苟杈撳嚭 CSV銆傚悗缁洖娴嬨€佹寚鏍囧拰绛栫暐浠ｇ爜鍙互鍦ㄧ嫭绔嬩笟鍔＄洰褰曚腑缁х画鎵╁睍銆?

## 鐩綍

```text
trader_US/
鈹溾攢鈹€ app/                         # 鍙洿鎺ヨ繍琛岀殑浠诲姟鍏ュ彛
鈹溾攢鈹€ data_sources/                # Alpha Vantage銆乊ahoo Finance 鏁版嵁婧?
鈹溾攢鈹€ earnings_calendar/           # 璐㈡姤鏃ュ巻涓氬姟閫昏緫涓?CSV 杈撳嚭
鈹溾攢鈹€ private_module/              # 椤圭洰鏃ュ織绛夌鏈夊叕鍏辨ā鍧?
鈹溾攢鈹€ standard_module/             # 鍙鐢ㄧ粺涓€閰嶇疆
鈹溾攢鈹€ output/                      # CSV 涓庢澘鍧楃紦瀛橈紝涓嶆彁浜?Git
鈹溾攢鈹€ logs/                        # 姣忔棩杩愯鏃ュ織锛屼笉鎻愪氦 Git
鈹溾攢鈹€ requirements.txt
鈹斺攢鈹€ test_calendar_service.py
```

## 浣跨敤

棣栨浣跨敤鏃跺鍒堕厤缃ā鏉匡細

```powershell
Copy-Item .\standard_module\config.example.py .\standard_module\config.py
```

鐒跺悗鍦ㄦ湰鍦?`standard_module/config.py` 涓～鍐欒嚜宸辩殑 Alpha Vantage API Key銆?
鐪熷疄閰嶇疆鏂囦欢宸茶 Git 蹇界暐锛屼笉浼氭彁浜わ紱鑲＄エ姹犮€佽姹傝秴鏃躲€佹帴鍙ｅ湴鍧€鍜岃緭鍑虹洰褰曚篃鍦ㄨ鏂囦欢缁存姢銆?

瀹夎渚濊禆锛?

```powershell
python -m pip install -r .\requirements.txt
```

鍛ㄤ竴杩愯锛?

```powershell
python .\app\earning_calendar_run.py
```

闈炲懆涓€鎵嬪伐杩愯锛?

```powershell
python .\app\earning_calendar_run.py --allow-any-day
```

鎸囧畾杩愯鏃ユ湡琛ヨ窇锛?

```powershell
python .\app\earning_calendar_run.py --run-date 2026-08-10
```

Windows 浠诲姟璁″垝绋嬪簭鍙缃负鍖椾含鏃堕棿姣忓懆涓€ 08:30锛氱▼搴忓～ `python`锛屽弬鏁板～
`D:\LeviPan\trader_US\app\earning_calendar_run.py`锛岃捣濮嬩綅缃～ `D:\LeviPan\trader_US`銆?
## 瀛楁璇存槑

- `status=ESTIMATED`锛欰lpha Vantage 鎻愪緵鐨勯鏈熸棩鏈燂紝骞堕潪鍏徃 IR 姝ｅ紡纭銆?
- `session=UNKNOWN`锛氳鎺ュ彛娌℃湁鍙潬鐨勭洏鍓?鐩樺悗鏃堕棿銆?
- `鎵€灞炴澘鍧梎 鏉ヨ嚜 yfinance `Ticker.get_info()` 鐨?`sector` 瀛楁锛孻ahoo 缂哄け鎴栬姹傚け璐ユ椂涓?`UNKNOWN`銆?- 鏉垮潡鍜岃涓氫俊鎭繚瀛樺湪 `output/company_profiles.sqlite3`锛岄粯璁ょ紦瀛?30 澶╋紝鍑忓皯閲嶅璇锋眰銆?- yfinance 浣跨敤 Yahoo 鐨勫叕寮€鎺ュ彛锛屽彲鑳藉嚭鐜伴檺娴佹垨瀛楁缂哄け锛屼笉搴斾綔涓轰氦鏄撳叧閿摼璺殑鍞竴鏁版嵁婧愩€?- 杈撳嚭鐩綍鍜岀湡瀹為厤缃潎琚?Git 蹇界暐銆?- 鏃ュ織鍚屾椂杈撳嚭鍒版帶鍒跺彴鍜?`logs/earning_calendar_YYYYMMDD.log`锛屽悓涓€澶╅噸澶嶈繍琛屼細杩藉姞璁板綍銆?
