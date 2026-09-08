#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 10:40
# software:Vscode
# brief : FMP数据下载和标准化离线测试

import json
import os
import tempfile
import unittest
from datetime import date

import pandas as pd

from strategy.fmp_data import (
    BALANCE_ENDPOINT,
    CASH_FLOW_ENDPOINT,
    EARNINGS_ENDPOINT,
    INCOME_ENDPOINT,
    KEY_METRICS_ENDPOINT,
    PRICE_ENDPOINT,
    RATIOS_ENDPOINT,
    FmpClient,
    download_fmp_dataset,
    fetch_earnings_calendar,
    map_earnings_session,
    transform_earnings_records,
    transform_fundamental_records,
    transform_price_records,
)


def build_statement_records() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    构造八个季度的FMP财务报表测试记录。

    :return: 利润表、资产负债表、现金流量表和比率记录
    """
    quarter_dates = pd.date_range("2024-03-31", periods=8, freq="QE")
    income_records = []
    balance_records = []
    cash_flow_records = []
    ratio_records = []
    for position, quarter_date in enumerate(quarter_dates):
        report_date = quarter_date.strftime("%Y-%m-%d")
        accepted_date = (quarter_date + pd.Timedelta(days=40)).strftime(
            "%Y-%m-%d 16:30:00"
        )
        income_records.append(
            {
                "date": report_date,
                "acceptedDate": accepted_date,
                "revenue": 100.0 + position * 10.0,
                "netIncome": 10.0 + position,
            }
        )
        balance_records.append(
            {
                "date": report_date,
                "acceptedDate": accepted_date,
                "totalAssets": 200.0,
                "totalLiabilities": 80.0,
                "totalStockholdersEquity": 100.0,
            }
        )
        cash_flow_records.append(
            {
                "date": report_date,
                "acceptedDate": accepted_date,
                "freeCashFlow": 10.0,
            }
        )
        ratio_records.append(
            {
                "date": report_date,
                "returnOnEquity": 0.20,
                "debtRatio": 0.40,
                "priceToEarningsRatio": 15.0,
            }
        )
    return income_records, balance_records, cash_flow_records, ratio_records


class FmpDataTestCase(unittest.TestCase):
    """验证FMP响应转换和下载编排。"""

    def test_price_adjustment_and_sorting(self) -> None:
        """
        验证复权因子同时作用于OHLC和成交量。

        :return: 无返回值
        """
        records = [
            {
                "date": "2026-01-06",
                "open": 102,
                "high": 104,
                "low": 100,
                "close": 102,
                "adjClose": 51,
                "volume": 1_000,
            },
            {
                "date": "2026-01-05",
                "open": 100,
                "high": 102,
                "low": 98,
                "close": 100,
                "adjClose": 50,
                "volume": 800,
            },
        ]

        data = transform_price_records(records, " aapl ")

        self.assertEqual(data.iloc[0]["symbol"], "AAPL")
        self.assertEqual(data.iloc[0]["open"], 50.0)
        self.assertEqual(data.iloc[0]["close"], 50.0)
        self.assertEqual(data.iloc[0]["volume"], 1_600.0)
        self.assertTrue(data["date"].is_monotonic_increasing)

    def test_dividend_adjusted_endpoint_fields(self) -> None:
        """
        验证FMP股息复权端点的adjOHLC字段可以直接转换。

        :return: 无返回值
        """
        data = transform_price_records(
            [
                {
                    "date": "2026-01-05",
                    "adjOpen": 50,
                    "adjHigh": 51,
                    "adjLow": 49,
                    "adjClose": 50.5,
                    "volume": 800,
                }
            ],
            "AAPL",
        )

        self.assertEqual(data.iloc[0]["open"], 50.0)
        self.assertEqual(data.iloc[0]["close"], 50.5)

    def test_fundamental_formulas_and_point_in_time(self) -> None:
        """
        验证同比增长、因子口径及发布时间。

        :return: 无返回值
        """
        statements = build_statement_records()

        data = transform_fundamental_records(
            "AAPL",
            *statements,
            key_metric_records=statements[3],
        )
        last_row = data.iloc[-1]

        self.assertAlmostEqual(last_row["revenue_growth"], 40 / 130)
        self.assertAlmostEqual(last_row["profit_growth"], 4 / 13)
        self.assertAlmostEqual(last_row["fcf_margin"], 10 / 170)
        self.assertAlmostEqual(last_row["roe"], 0.20)
        self.assertAlmostEqual(last_row["debt_ratio"], 0.40)
        self.assertAlmostEqual(last_row["pe"], 15.0)
        self.assertGreaterEqual(
            last_row["published_at"],
            last_row["fiscal_period_end"],
        )

    def test_earnings_mapping_shares_event_id(self) -> None:
        """
        验证财报日历与结果表共用稳定事件编号。

        :return: 无返回值
        """
        records = [
            {
                "date": "2026-01-29",
                "symbol": "AAPL",
                "time": "bmo",
                "epsActual": -0.1,
                "epsEstimated": -0.2,
                "revenueActual": 100,
                "revenueEstimated": 90,
            }
        ]

        calendar, results = transform_earnings_records(records, ["AAPL"])

        self.assertEqual(calendar.iloc[0]["event_id"], results.iloc[0]["event_id"])
        self.assertEqual(calendar.iloc[0]["session"], "BMO")
        self.assertEqual(results.iloc[0]["actual_eps"], -0.1)
        self.assertEqual(calendar.iloc[0]["status"], "ASSUMED")

    def test_session_mapping_and_unknown_policy(self) -> None:
        """
        验证常见财报时段及缺失值策略。

        :return: 无返回值
        """
        cases = {
            "pre-market": "BMO",
            "before market open": "BMO",
            "post-market": "AMC",
            "after market close": "AMC",
        }
        for source_value, expected_value in cases.items():
            with self.subTest(source_value=source_value):
                self.assertEqual(map_earnings_session(source_value), expected_value)
        self.assertEqual(map_earnings_session(None, "AMC"), "AMC")
        self.assertEqual(map_earnings_session("unknown", "TBD"), "TBD")

    def test_calendar_chunking_has_no_date_gap(self) -> None:
        """
        验证长日期区间按连续小段请求。

        :return: 无返回值
        """
        requests = []

        def fake_requester(endpoint: str, params: dict) -> list[dict]:
            """
            记录离线请求参数。

            :param endpoint: API端点
            :param params: 查询参数
            :return: 空记录
            """
            requests.append((endpoint, params))
            return []

        client = FmpClient(api_key="test-key", requester=fake_requester)
        fetch_earnings_calendar(
            client,
            date(2026, 1, 1),
            date(2026, 1, 5),
            chunk_days=2,
        )

        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[0][1]["from"], "2026-01-01")
        self.assertEqual(requests[1][1]["from"], "2026-01-03")
        self.assertEqual(requests[2][1]["to"], "2026-01-05")

    def test_api_error_payload_does_not_expose_key(self) -> None:
        """
        验证API错误被识别且异常不包含API Key。

        :return: 无返回值
        """
        client = FmpClient(
            api_key="secret-key",
            requester=lambda endpoint, params: {"Error Message": "denied"},
        )

        with self.assertRaises(RuntimeError) as context:
            client.get("test", {})

        self.assertNotIn("secret-key", str(context.exception))

    def test_full_bundle_is_written_without_network(self) -> None:
        """
        验证离线假响应可以生成完整回测数据包。

        :return: 无返回值
        """
        statements = build_statement_records()
        price_records = [
            {
                "date": "2026-01-05",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 1_000,
            }
        ]
        earnings_records = [
            {
                "date": "2026-01-29",
                "symbol": "AAPL",
                "time": "amc",
                "epsActual": 1.1,
                "epsEstimated": 1.0,
                "revenueActual": 110,
                "revenueEstimated": 100,
            }
        ]
        responses = {
            PRICE_ENDPOINT: price_records,
            INCOME_ENDPOINT: statements[0],
            BALANCE_ENDPOINT: statements[1],
            CASH_FLOW_ENDPOINT: statements[2],
            RATIOS_ENDPOINT: statements[3],
            KEY_METRICS_ENDPOINT: statements[3],
            EARNINGS_ENDPOINT: earnings_records,
        }

        def fake_requester(endpoint: str, params: dict) -> list[dict]:
            """
            返回端点对应的离线响应，财报日历第二页返回空列表。

            :param endpoint: API端点
            :param params: 查询参数
            :return: 离线响应记录
            """
            if endpoint == EARNINGS_ENDPOINT and params.get("page", 0) > 0:
                return []
            return responses[endpoint]

        client = FmpClient(
            api_key="test-key",
            requester=fake_requester,
        )

        with tempfile.TemporaryDirectory() as output_dir:
            output_paths = download_fmp_dataset(
                client,
                ["AAPL"],
                date(2026, 1, 1),
                date(2026, 1, 31),
                os.path.abspath(output_dir),
            )

            for output_path in output_paths.values():
                self.assertTrue(os.path.isfile(output_path))
            with open(
                output_paths["manifest"],
                "r",
                encoding="utf-8",
            ) as manifest_file:
                manifest = json.load(manifest_file)
            self.assertEqual(manifest["row_counts"]["calendar"], 1)


if __name__ == "__main__":
    unittest.main()
