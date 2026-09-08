#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 10:20
# software:Vscode
# brief : FMP回测数据下载与标准化

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


logger = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"
PRICE_ENDPOINT = "historical-price-eod/dividend-adjusted"
INCOME_ENDPOINT = "income-statement"
BALANCE_ENDPOINT = "balance-sheet-statement"
CASH_FLOW_ENDPOINT = "cash-flow-statement"
RATIOS_ENDPOINT = "ratios"
KEY_METRICS_ENDPOINT = "key-metrics"
EARNINGS_ENDPOINT = "earnings-calendar"

PRICE_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
FUNDAMENTAL_COLUMNS = [
    "symbol",
    "fiscal_period_end",
    "published_at",
    "roe",
    "revenue_growth",
    "profit_growth",
    "fcf_margin",
    "debt_ratio",
    "pe",
]
CALENDAR_COLUMNS = [
    "event_id",
    "symbol",
    "report_date",
    "session",
    "known_at",
    "status",
    "source",
]
RESULT_COLUMNS = [
    "event_id",
    "symbol",
    "release_at",
    "actual_eps",
    "consensus_eps",
    "actual_revenue",
    "consensus_revenue",
]

FmpRequester = Callable[[str, dict[str, Any]], object]


@dataclass
class FmpClient:
    """
    访问FMP Stable REST API。

    :param api_key: FMP API Key
    :param base_url: Stable API根地址
    :param timeout: 单次请求超时秒数
    :param maximum_retries: 可恢复错误最大重试次数
    :param retry_delay: 首次重试等待秒数，后续指数退避
    :param requester: 测试时注入的离线请求函数
    :return: FMP客户端对象
    """

    api_key: str
    base_url: str = FMP_BASE_URL
    timeout: int = 30
    maximum_retries: int = 3
    retry_delay: float = 1.0
    requester: FmpRequester | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """
        校验客户端参数并清理地址。

        :return: 无返回值
        """
        if not self.api_key or self.api_key == "YOUR_FMP_API_KEY":
            raise ValueError("请先配置有效的FMP_API_KEY")
        if self.timeout <= 0:
            raise ValueError("timeout必须大于0")
        if self.maximum_retries < 0 or self.retry_delay < 0:
            raise ValueError("重试参数不能小于0")
        self.base_url = self.base_url.rstrip("/")

    def get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        请求一个FMP端点并标准化为记录列表。

        :param endpoint: Stable API相对端点
        :param params: 查询参数，不包含API Key
        :return: JSON记录列表
        """
        if self.requester is not None:
            return self._normalize_payload(self.requester(endpoint, dict(params)))

        query_params = {
            key: value
            for key, value in params.items()
            if value is not None
        }
        query_params["apikey"] = self.api_key
        url = f"{self.base_url}/{endpoint.lstrip('/')}?{urlencode(query_params)}"

        for attempt in range(self.maximum_retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "trader-US-earnings-backtest/1.0",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return self._normalize_payload(payload)
            except HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise RuntimeError(
                        f"FMP接口{endpoint}请求失败，HTTP状态码={exc.code}"
                    ) from exc
                last_error = exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < self.maximum_retries:
                time.sleep(self.retry_delay * (2 ** attempt))

        raise RuntimeError(
            f"FMP接口{endpoint}重试后仍然失败"
        ) from last_error

    @staticmethod
    def _normalize_payload(payload: object) -> list[dict[str, Any]]:
        """
        检查FMP响应并提取记录列表。

        :param payload: 已解析的JSON响应
        :return: 记录列表
        """
        if isinstance(payload, dict):
            error_message = next(
                (
                    payload[key]
                    for key in ("Error Message", "error", "message", "Information")
                    if payload.get(key)
                ),
                None,
            )
            if error_message is not None:
                raise RuntimeError(f"FMP返回错误：{error_message}")
            for container_key in ("historical", "data"):
                if isinstance(payload.get(container_key), list):
                    payload = payload[container_key]
                    break
            else:
                payload = [payload]
        if not isinstance(payload, list):
            raise RuntimeError("FMP响应不是预期的JSON数组")
        if any(not isinstance(record, dict) for record in payload):
            raise RuntimeError("FMP响应数组中存在非对象记录")
        return payload


def normalize_symbols(symbols: Sequence[str]) -> list[str]:
    """
    清理股票代码、去重并保持输入顺序。

    :param symbols: 原始股票代码序列
    :return: 标准化股票代码列表
    """
    normalized_symbols = []
    seen_symbols = set()
    for symbol in symbols:
        normalized_symbol = str(symbol).strip().upper()
        if normalized_symbol and normalized_symbol not in seen_symbols:
            normalized_symbols.append(normalized_symbol)
            seen_symbols.add(normalized_symbol)
    if not normalized_symbols:
        raise ValueError("至少需要提供一个股票代码")
    return normalized_symbols


def transform_price_records(
    records: Sequence[dict[str, Any]],
    symbol: str,
) -> pd.DataFrame:
    """
    将FMP日线行情转换为回测价格表。

    存在adjClose时使用相同比例调整OHLC，并反向调整成交量；缺少
    adjClose时保留FMP原始OHLCV。

    :param records: FMP历史价格记录
    :param symbol: 股票代码
    :return: 标准价格数据
    """
    if not records:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    data = pd.DataFrame(records).copy()
    adjusted_columns = {"adjOpen", "adjHigh", "adjLow", "adjClose"}
    has_adjusted_ohlc = adjusted_columns.issubset(data.columns)
    if has_adjusted_ohlc:
        data["open"] = data["adjOpen"]
        data["high"] = data["adjHigh"]
        data["low"] = data["adjLow"]
        data["close"] = data["adjClose"]
    required_columns = {"date", "open", "high", "low", "close", "volume"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        raise ValueError(f"FMP行情缺少字段：{sorted(missing_columns)}")

    numeric_columns = ["open", "high", "low", "close", "volume"]
    data[numeric_columns] = data[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    if "adjClose" in data.columns and not has_adjusted_ohlc:
        data["adjClose"] = pd.to_numeric(data["adjClose"], errors="coerce")
        adjustment_factor = data["adjClose"] / data["close"]
        valid_factor = adjustment_factor.notna() & (adjustment_factor > 0)
        for column in ("open", "high", "low", "close"):
            data.loc[valid_factor, column] = (
                data.loc[valid_factor, column] * adjustment_factor[valid_factor]
            )
        data.loc[valid_factor, "volume"] = (
            data.loc[valid_factor, "volume"] / adjustment_factor[valid_factor]
        )

    data["symbol"] = symbol.strip().upper()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=PRICE_COLUMNS)
    data = data.loc[
        (data["open"] > 0)
        & (data["high"] > 0)
        & (data["low"] > 0)
        & (data["close"] > 0)
        & (data["volume"] >= 0)
    ]
    invalid_ohlc = (
        (data["high"] < data[["open", "close", "low"]].max(axis=1))
        | (data["low"] > data[["open", "close", "high"]].min(axis=1))
    )
    if invalid_ohlc.any():
        raise ValueError(f"{symbol}行情存在不合法的OHLC关系")
    return data[PRICE_COLUMNS].sort_values("date").drop_duplicates(
        ["symbol", "date"],
        keep="last",
    ).reset_index(drop=True)


def _statement_frame(
    records: Sequence[dict[str, Any]],
    value_aliases: dict[str, tuple[str, ...]],
    source_name: str,
) -> pd.DataFrame:
    """
    从一类FMP财务记录提取统一字段。

    :param records: FMP财务记录
    :param value_aliases: 目标字段到候选源字段的映射
    :param source_name: 数据源名称，用于发布时间字段后缀
    :return: 按报告期整理的财务数据
    """
    output_columns = [
        "fiscal_period_end",
        f"published_at_{source_name}",
        *value_aliases,
    ]
    if not records:
        return pd.DataFrame(columns=output_columns)

    data = pd.DataFrame(records)
    if "date" not in data.columns:
        raise ValueError("FMP财务数据缺少date字段")
    output = pd.DataFrame()
    output["fiscal_period_end"] = pd.to_datetime(data["date"], errors="coerce")
    published_at = pd.Series(pd.NaT, index=data.index, dtype="datetime64[ns]")
    for column in ("acceptedDate", "fillingDate", "filingDate"):
        if column in data.columns:
            candidate = pd.to_datetime(data[column], errors="coerce")
            published_at = published_at.fillna(candidate)
    output[f"published_at_{source_name}"] = published_at

    for target_column, source_columns in value_aliases.items():
        values = pd.Series(float("nan"), index=data.index, dtype="float64")
        for source_column in source_columns:
            if source_column in data.columns:
                values = values.fillna(
                    pd.to_numeric(data[source_column], errors="coerce")
                )
        output[target_column] = values

    return output.dropna(subset=["fiscal_period_end"]).drop_duplicates(
        "fiscal_period_end",
        keep="first",
    )


def transform_fundamental_records(
    symbol: str,
    income_records: Sequence[dict[str, Any]],
    balance_records: Sequence[dict[str, Any]],
    cash_flow_records: Sequence[dict[str, Any]],
    ratio_records: Sequence[dict[str, Any]],
    key_metric_records: Sequence[dict[str, Any]] = (),
) -> pd.DataFrame:
    """
    将FMP季度财务报表转换为策略基本面因子。

    收入和净利润增长率按上一年同季度计算。published_at取参与计算的
    报表最晚可用时间，避免在正式披露以前使用数据。

    :param symbol: 股票代码
    :param income_records: 季度利润表
    :param balance_records: 季度资产负债表
    :param cash_flow_records: 季度现金流量表
    :param ratio_records: 季度财务比率
    :param key_metric_records: 季度关键指标
    :return: 标准基本面数据
    """
    income = _statement_frame(
        income_records,
        {
            "revenue": ("revenue",),
            "net_income": ("netIncome",),
        },
        "income",
    )
    if income.empty:
        return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

    balance = _statement_frame(
        balance_records,
        {
            "total_assets": ("totalAssets",),
            "total_liabilities": ("totalLiabilities",),
            "total_debt": ("totalDebt",),
            "total_equity": (
                "totalStockholdersEquity",
                "totalEquity",
            ),
        },
        "balance",
    )
    cash_flow = _statement_frame(
        cash_flow_records,
        {"free_cash_flow": ("freeCashFlow",)},
        "cash_flow",
    )
    ratios = _statement_frame(
        ratio_records,
        {
            "reported_debt_ratio": (
                "debtToAssetsRatio",
                "debtRatio",
            ),
            "reported_pe": (
                "priceToEarningsRatio",
                "priceEarningsRatio",
            ),
        },
        "ratios",
    )
    key_metrics = _statement_frame(
        key_metric_records,
        {"reported_roe": ("returnOnEquity",)},
        "key_metrics",
    )

    data = income.sort_values("fiscal_period_end").copy()
    for additional_data in (balance, cash_flow, ratios, key_metrics):
        data = data.merge(
            additional_data,
            on="fiscal_period_end",
            how="left",
            validate="one_to_one",
        )

    numeric_source_columns = [
        "revenue",
        "net_income",
        "total_assets",
        "total_liabilities",
        "total_debt",
        "total_equity",
        "free_cash_flow",
        "reported_roe",
        "reported_debt_ratio",
        "reported_pe",
    ]
    data[numeric_source_columns] = data[numeric_source_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    previous_revenue = data["revenue"].shift(4)
    previous_profit = data["net_income"].shift(4)
    data["revenue_growth"] = (
        (data["revenue"] - previous_revenue) / previous_revenue.abs()
    ).where(previous_revenue != 0)
    data["profit_growth"] = (
        (data["net_income"] - previous_profit) / previous_profit.abs()
    ).where(previous_profit != 0)
    data["fcf_margin"] = data["free_cash_flow"] / data["revenue"]
    calculated_roe = data["net_income"] / data["total_equity"]
    data["roe"] = data["reported_roe"].fillna(calculated_roe)
    calculated_debt_ratio = data["total_debt"].fillna(
        data["total_liabilities"]
    ) / data["total_assets"]
    data["debt_ratio"] = data["reported_debt_ratio"].fillna(
        calculated_debt_ratio
    )
    data["pe"] = data["reported_pe"]
    data.loc[data["pe"] <= 0, "pe"] = pd.NA

    published_columns = [
        column for column in data.columns
        if column.startswith("published_at_")
    ]
    published_data = data[published_columns].apply(
        pd.to_datetime,
        errors="coerce",
    )
    data["published_at"] = published_data.max(axis=1)
    data["published_at"] = data["published_at"].fillna(
        data["fiscal_period_end"] + pd.Timedelta(days=90)
    )
    data["symbol"] = symbol.strip().upper()

    for column in (
        "roe",
        "revenue_growth",
        "profit_growth",
        "fcf_margin",
        "debt_ratio",
        "pe",
    ):
        data[column] = pd.to_numeric(data[column], errors="coerce")
        data.loc[~data[column].map(_is_finite), column] = pd.NA

    return data[FUNDAMENTAL_COLUMNS].sort_values(
        "fiscal_period_end"
    ).reset_index(drop=True)


def _is_finite(value: Any) -> bool:
    """
    判断数值是否有限。

    :param value: 待判断值
    :return: 有限数值返回True
    """
    try:
        return pd.notna(value) and abs(float(value)) != float("inf")
    except (TypeError, ValueError):
        return False


def map_earnings_session(value: Any, unknown_session: str = "TBD") -> str:
    """
    将FMP财报时段映射为策略枚举值。

    :param value: FMP time或hour字段
    :param unknown_session: 无法识别时使用的BMO、AMC或TBD
    :return: BMO、AMC或TBD
    """
    if unknown_session not in {"BMO", "AMC", "TBD"}:
        raise ValueError("unknown_session必须为BMO、AMC或TBD")
    normalized_value = str(value or "").strip().lower()
    if normalized_value in {
        "bmo",
        "before market open",
        "before_open",
        "before-open",
        "pre-market",
        "premarket",
    }:
        return "BMO"
    if normalized_value in {
        "amc",
        "after market close",
        "after_close",
        "after-close",
        "post-market",
        "postmarket",
    }:
        return "AMC"
    return unknown_session


def transform_earnings_records(
    records: Sequence[dict[str, Any]],
    symbols: Sequence[str],
    assumed_known_days: int = 30,
    unknown_session: str = "AMC",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    将FMP财报日历同时转换为事件表和实际结果表。

    FMP历史日历通常不提供发布日期何时被市场知晓的完整修订历史，因此
    known_at按财报日前指定自然日数构造，并将状态标记为ESTIMATED。

    :param records: FMP财报日历记录
    :param symbols: 需要保留的股票代码
    :param assumed_known_days: 假设市场提前知道日期的自然日数
    :param unknown_session: FMP缺少时段时采用的保守时段假设
    :return: 标准财报日历和财报结果
    """
    if assumed_known_days < 0:
        raise ValueError("assumed_known_days不能小于0")
    selected_symbols = set(normalize_symbols(symbols))
    calendar_rows = []
    result_rows = []

    for record in records:
        symbol = str(record.get("symbol", "")).strip().upper()
        report_timestamp = pd.to_datetime(record.get("date"), errors="coerce")
        if symbol not in selected_symbols or pd.isna(report_timestamp):
            continue

        report_date = report_timestamp.date()
        session = map_earnings_session(
            record.get(
                "reportTime",
                record.get(
                    "reportingTime",
                    record.get("time", record.get("hour", record.get("when"))),
                ),
            ),
            unknown_session,
        )
        event_id = f"{symbol}_{report_date.strftime('%Y%m%d')}"
        known_at = datetime.combine(
            report_date - timedelta(days=assumed_known_days),
            datetime_time(0, 0),
        )
        release_clock = {
            "BMO": datetime_time(8, 0),
            "AMC": datetime_time(16, 5),
            "TBD": datetime_time(16, 5),
        }[session]
        calendar_rows.append(
            {
                "event_id": event_id,
                "symbol": symbol,
                "report_date": report_date,
                "session": session,
                "known_at": known_at,
                "status": "ASSUMED",
                "source": f"FMP_ASSUMED_{assumed_known_days}D",
            }
        )
        result_rows.append(
            {
                "event_id": event_id,
                "symbol": symbol,
                "release_at": datetime.combine(report_date, release_clock),
                "actual_eps": record.get("epsActual"),
                "consensus_eps": record.get("epsEstimated"),
                "actual_revenue": record.get("revenueActual"),
                "consensus_revenue": record.get("revenueEstimated"),
            }
        )

    calendar = pd.DataFrame(calendar_rows, columns=CALENDAR_COLUMNS)
    results = pd.DataFrame(result_rows, columns=RESULT_COLUMNS)
    if not calendar.empty:
        calendar = calendar.sort_values(
            ["report_date", "symbol"]
        ).drop_duplicates("event_id", keep="last").reset_index(drop=True)
        results = results.loc[results["event_id"].isin(calendar["event_id"])]
        results = results.sort_values(
            ["release_at", "symbol"]
        ).drop_duplicates("event_id", keep="last").reset_index(drop=True)
    return calendar, results


def fetch_earnings_calendar(
    client: FmpClient,
    start_date: date,
    end_date: date,
    chunk_days: int = 90,
    maximum_pages: int = 1_000,
) -> list[dict[str, Any]]:
    """
    分段下载FMP财报日历，避免接口日期跨度限制。

    :param client: FMP客户端
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param chunk_days: 单次请求最大自然日数
    :param maximum_pages: 每个日期分段允许的最大页数
    :return: 合并后的财报记录
    """
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")
    if chunk_days <= 0:
        raise ValueError("chunk_days必须大于0")
    if maximum_pages <= 0:
        raise ValueError("maximum_pages必须大于0")

    records = []
    current_date = start_date
    while current_date <= end_date:
        chunk_end = min(
            current_date + timedelta(days=chunk_days - 1),
            end_date,
        )
        page_signatures = set()
        for page in range(maximum_pages):
            page_records = client.get(
                EARNINGS_ENDPOINT,
                {
                    "from": current_date.isoformat(),
                    "to": chunk_end.isoformat(),
                    "page": page,
                    "includeReportTimes": "true",
                },
            )
            if not page_records:
                break
            page_signature = json.dumps(
                page_records,
                sort_keys=True,
                default=str,
            )
            if page_signature in page_signatures:
                raise RuntimeError("FMP财报日历返回重复分页，已停止下载")
            page_signatures.add(page_signature)
            records.extend(page_records)
        else:
            raise RuntimeError("FMP财报日历分页超过安全上限")
        current_date = chunk_end + timedelta(days=1)
    return records


def download_fmp_dataset(
    client: FmpClient,
    symbols: Sequence[str],
    start_date: date,
    end_date: date,
    output_dir: str,
    assumed_known_days: int = 30,
    unknown_session: str = "AMC",
) -> dict[str, str]:
    """
    下载并生成回测所需的四份标准CSV。

    :param client: FMP客户端
    :param symbols: 股票代码列表
    :param start_date: 行情和财报开始日期
    :param end_date: 行情和财报结束日期
    :param output_dir: 绝对输出目录
    :param assumed_known_days: 财报日期已知时间的假设提前天数
    :param unknown_session: FMP缺少财报时段时采用的时段假设
    :return: 输出文件名到绝对路径的映射
    """
    if not os.path.isabs(output_dir):
        raise ValueError("output_dir必须使用绝对路径")
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")

    normalized_symbols = normalize_symbols(symbols)
    quarter_limit = max(12, (end_date.year - start_date.year + 2) * 4)
    price_frames = []
    fundamental_frames = []

    for position, symbol in enumerate(normalized_symbols, start=1):
        logger.info(
            "下载FMP数据，股票=%s，进度=%s/%s",
            symbol,
            position,
            len(normalized_symbols),
        )
        price_frames.append(
            transform_price_records(
                client.get(
                    PRICE_ENDPOINT,
                    {
                        "symbol": symbol,
                        "from": start_date.isoformat(),
                        "to": end_date.isoformat(),
                    },
                ),
                symbol,
            )
        )
        statement_params = {
            "symbol": symbol,
            "period": "quarter",
            "limit": quarter_limit,
        }
        fundamental_frames.append(
            transform_fundamental_records(
                symbol,
                client.get(INCOME_ENDPOINT, statement_params),
                client.get(BALANCE_ENDPOINT, statement_params),
                client.get(CASH_FLOW_ENDPOINT, statement_params),
                client.get(RATIOS_ENDPOINT, statement_params),
                client.get(KEY_METRICS_ENDPOINT, statement_params),
            )
        )

    prices = pd.concat(price_frames, ignore_index=True)
    fundamentals = pd.concat(fundamental_frames, ignore_index=True)
    earnings_records = fetch_earnings_calendar(client, start_date, end_date)
    calendar, results = transform_earnings_records(
        earnings_records,
        normalized_symbols,
        assumed_known_days,
        unknown_session,
    )
    if prices.empty:
        raise RuntimeError("FMP未返回任何有效行情数据")
    if fundamentals.empty:
        raise RuntimeError("FMP未返回任何有效基本面数据")
    if calendar.empty:
        raise RuntimeError("FMP未返回所选股票的财报日历")

    os.makedirs(output_dir, exist_ok=True)
    output_paths = {
        "prices": os.path.join(output_dir, "prices.csv"),
        "fundamentals": os.path.join(output_dir, "fundamentals.csv"),
        "calendar": os.path.join(output_dir, "earnings_calendar.csv"),
        "results": os.path.join(output_dir, "earnings_results.csv"),
        "manifest": os.path.join(output_dir, "dataset_manifest.json"),
    }
    for name, data in (
        ("prices", prices),
        ("fundamentals", fundamentals),
        ("calendar", calendar),
        ("results", results),
    ):
        data.to_csv(output_paths[name], index=False, encoding="utf-8-sig")

    manifest = {
        "provider": "Financial Modeling Prep",
        "api_namespace": client.base_url,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": normalized_symbols,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "known_at_policy": f"report_date_minus_{assumed_known_days}_calendar_days",
        "unknown_session_policy": unknown_session,
        "fundamental_published_at_policy": (
            "latest acceptedDate or filingDate; fiscal period end plus 90 days fallback"
        ),
        "point_in_time_warning": (
            "FMP历史日历不包含完整日期修订历史，known_at为研究假设，"
            "不能视为严格Point-in-Time数据"
        ),
        "row_counts": {
            "prices": len(prices),
            "fundamentals": len(fundamentals),
            "calendar": len(calendar),
            "results": len(results),
        },
    }
    with open(output_paths["manifest"], "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=False, indent=2)
    return output_paths
