#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : 财报日历核心业务测试

import unittest
from datetime import date

from earnings_calendar.calendar_service import filter_next_week, get_earnings_sort_key


class CalendarServiceTest(unittest.TestCase):
    """财报筛选和排序测试。"""

    def test_sector_session_and_estimate_sort(self):
        """
        验证盘前、盘后与 EPS 降序规则。

        :return: 无
        """
        rows = [
            {"symbol": "POST", "reportDate": "2026-08-18", "estimate": "5", "timeOfTheDay": "post-market"},
            {"symbol": "PRE_LOW", "reportDate": "2026-08-18", "estimate": "1", "timeOfTheDay": "pre-market"},
            {"symbol": "PRE_HIGH", "reportDate": "2026-08-18", "estimate": "3", "timeOfTheDay": "pre-market"},
        ]
        filtered = filter_next_week(rows, date(2026, 8, 17), date(2026, 8, 23), [])
        result = sorted(filtered, key=get_earnings_sort_key)
        self.assertEqual([row["symbol"] for row in result], ["PRE_HIGH", "PRE_LOW", "POST"])


if __name__ == "__main__":
    unittest.main()
