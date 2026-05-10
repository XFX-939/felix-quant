import unittest

import pandas as pd

from app.services.akshare_provider import AkshareDataProvider, normalize_stock_code


class FakeAkshare:
    def stock_zh_a_spot_em(self):
        return pd.DataFrame(
            [
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "最新价": 12.34,
                    "涨跌幅": 1.23,
                    "成交量": 123456,
                    "成交额": 1500000000,
                    "今开": 12.1,
                    "最高": 12.5,
                    "最低": 12.0,
                    "流通市值": 200000000000,
                },
                {
                    "代码": "600036",
                    "名称": "招商银行",
                    "最新价": 42.6,
                    "涨跌幅": -0.5,
                    "成交量": 456789,
                    "成交额": 2100000000,
                    "今开": 42.8,
                    "最高": 43.2,
                    "最低": 42.1,
                    "流通市值": 300000000000,
                },
            ]
        )

    def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
        self.hist_args = {
            "symbol": symbol,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "adjust": adjust,
        }
        return pd.DataFrame(
            [
                {
                    "日期": "2026-05-04",
                    "股票代码": symbol,
                    "开盘": 12.0,
                    "收盘": 12.2,
                    "最高": 12.4,
                    "最低": 11.9,
                    "成交量": 100000,
                    "成交额": 122000000,
                    "涨跌幅": 1.67,
                },
                {
                    "日期": "2026-05-05",
                    "股票代码": symbol,
                    "开盘": 12.2,
                    "收盘": 12.48,
                    "最高": 12.48,
                    "最低": 12.1,
                    "成交量": 110000,
                    "成交额": 137280000,
                    "涨跌幅": 2.3,
                },
            ]
        )

    def stock_zt_pool_em(self, date):
        self.limit_pool_date = date
        return pd.DataFrame(
            [
                {
                    "代码": "002281",
                    "名称": "光迅科技",
                    "最新价": 33.6,
                    "涨跌幅": 10.0,
                    "成交额": 2600000000,
                    "换手率": 12.3,
                    "流通市值": 42000000000,
                    "连板数": "3天3板",
                    "炸板次数": 1,
                    "首次封板时间": 93000,
                    "最后封板时间": 145700,
                    "封板资金": 520000000,
                    "所属行业": "通信",
                }
            ]
        )


class FakeAkshareSpotFails:
    def stock_zh_a_spot_em(self):
        raise ConnectionError("Remote end closed connection without response")

    def stock_info_a_code_name(self):
        return pd.DataFrame(
            [
                {"code": "000001", "name": "平安银行"},
                {"code": "300308", "name": "中际旭创"},
                {"code": "688981", "name": "中芯国际"},
            ]
        )


class FakeAkshareRealtimeFallback:
    def stock_zh_a_spot_em(self):
        raise ConnectionError("Remote end closed connection without response")

    def stock_zh_a_spot(self):
        return pd.DataFrame(
            [
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "最新价": 12.34,
                    "涨跌幅": 1.23,
                    "成交量": 123456,
                    "成交额": 1500000000,
                    "昨收": 12.19,
                    "今开": 12.1,
                    "最高": 12.5,
                    "最低": 12.0,
                },
                {
                    "代码": "600036",
                    "名称": "招商银行",
                    "最新价": 42.6,
                    "涨跌幅": -0.5,
                    "成交量": 456789,
                    "成交额": 2100000000,
                    "昨收": 42.81,
                    "今开": 42.8,
                    "最高": 43.2,
                    "最低": 42.1,
                },
            ]
        )


class FakeAkshareHistFails(FakeAkshare):
    def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
        raise ConnectionError("Remote end closed connection without response")

    def stock_zh_a_daily(self, symbol, start_date, end_date, adjust):
        self.daily_args = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "adjust": adjust,
        }
        return pd.DataFrame(
            [
                {
                    "date": "2026-05-04",
                    "open": 10.0,
                    "high": 10.4,
                    "low": 9.9,
                    "close": 10.2,
                    "volume": 1200000,
                    "amount": 12240000,
                },
                {
                    "date": "2026-05-05",
                    "open": 10.2,
                    "high": 10.8,
                    "low": 10.1,
                    "close": 10.71,
                    "volume": 1500000,
                    "amount": 16065000,
                },
            ]
        )


class AkshareProviderTest(unittest.TestCase):
    def test_normalize_stock_code_strips_market_suffixes(self):
        self.assertEqual(normalize_stock_code("sz000001"), "000001")
        self.assertEqual(normalize_stock_code("600036.SH"), "600036")
        self.assertEqual(normalize_stock_code(" 300750 "), "300750")

    def test_fetch_stock_universe_maps_spot_fields(self):
        provider = AkshareDataProvider(FakeAkshare())

        stocks = provider.fetch_stock_universe(limit=2)

        self.assertEqual(stocks[0]["code"], "000001")
        self.assertEqual(stocks[0]["name"], "平安银行")
        self.assertEqual(stocks[0]["market"], "SZ")
        self.assertEqual(stocks[0]["industry"], "未分类")
        self.assertEqual(stocks[0]["float_market_cap"], 200000000000)
        self.assertFalse(stocks[0]["is_st"])
        self.assertFalse(stocks[0]["is_suspended"])
        self.assertEqual(stocks[1]["market"], "SH")

    def test_fetch_stock_universe_falls_back_to_basic_code_table(self):
        provider = AkshareDataProvider(FakeAkshareSpotFails())

        stocks = provider.fetch_stock_universe(limit=2)

        self.assertEqual([stock["code"] for stock in stocks], ["000001", "300308"])
        self.assertEqual(stocks[1]["name"], "中际旭创")
        self.assertEqual(stocks[1]["market"], "SZ")
        self.assertEqual(stocks[1]["industry"], "未分类")
        self.assertFalse(stocks[1]["is_st"])
        self.assertFalse(stocks[1]["is_suspended"])

    def test_fetch_stock_universe_falls_back_to_realtime_spot(self):
        provider = AkshareDataProvider(FakeAkshareRealtimeFallback())

        stocks = provider.fetch_stock_universe(limit=2)

        self.assertEqual([stock["code"] for stock in stocks], ["000001", "600036"])
        self.assertEqual(stocks[0]["name"], "平安银行")
        self.assertFalse(stocks[0]["is_suspended"])

    def test_fetch_market_snapshot_falls_back_to_realtime_spot(self):
        provider = AkshareDataProvider(FakeAkshareRealtimeFallback())

        rows = provider.fetch_market_snapshot(limit=2)

        self.assertEqual([row["stock_code"] for row in rows], ["000001", "600036"])
        self.assertEqual(rows[0]["stock_name"], "平安银行")
        self.assertEqual(rows[0]["close"], 12.34)
        self.assertEqual(rows[0]["pre_close"], 12.19)
        self.assertEqual(rows[0]["change_pct"], 1.23)
        self.assertFalse(rows[0]["is_suspended"])

    def test_fetch_daily_prices_maps_hist_fields_and_units(self):
        fake_ak = FakeAkshare()
        provider = AkshareDataProvider(fake_ak)

        prices = provider.fetch_daily_prices("sz000001", "20260501", "20260505", adjust="qfq")

        self.assertEqual(fake_ak.hist_args["symbol"], "000001")
        self.assertEqual(fake_ak.hist_args["period"], "daily")
        self.assertEqual(fake_ak.hist_args["adjust"], "qfq")
        self.assertEqual(prices[-1]["stock_code"], "000001")
        self.assertEqual(prices[-1]["date"], "2026-05-05")
        self.assertEqual(prices[-1]["close"], 12.48)
        self.assertEqual(prices[-1]["volume"], 11000000)
        self.assertEqual(prices[-1]["amount"], 137280000)
        self.assertEqual(prices[-1]["pct_change"], 2.3)

    def test_fetch_daily_prices_falls_back_to_sina_daily(self):
        fake_ak = FakeAkshareHistFails()
        provider = AkshareDataProvider(fake_ak)

        prices = provider.fetch_daily_prices("000001", "20260501", "20260505", adjust="qfq")

        self.assertEqual(fake_ak.daily_args["symbol"], "sz000001")
        self.assertEqual(fake_ak.daily_args["start_date"], "20260501")
        self.assertEqual(fake_ak.daily_args["end_date"], "20260505")
        self.assertEqual(fake_ak.daily_args["adjust"], "qfq")
        self.assertEqual(prices[-1]["stock_code"], "000001")
        self.assertEqual(prices[-1]["date"], "2026-05-05")
        self.assertEqual(prices[-1]["close"], 10.71)
        self.assertEqual(prices[-1]["volume"], 1500000)
        self.assertEqual(prices[-1]["pct_change"], 5.0)

    def test_fetch_limit_up_pool_maps_board_count_and_seal_fields(self):
        fake_ak = FakeAkshare()
        provider = AkshareDataProvider(fake_ak)

        rows = provider.fetch_limit_up_pool("2026-05-08")

        self.assertEqual(fake_ak.limit_pool_date, "20260508")
        self.assertEqual(rows[0]["stock_code"], "002281")
        self.assertEqual(rows[0]["stock_name"], "光迅科技")
        self.assertEqual(rows[0]["industry"], "通信")
        self.assertEqual(rows[0]["board_count"], 3)
        self.assertEqual(rows[0]["open_board_count"], 1)
        self.assertEqual(rows[0]["first_limit_time"], "09:30:00")
        self.assertEqual(rows[0]["last_limit_time"], "14:57:00")
        self.assertEqual(rows[0]["seal_amount"], 520000000)
        self.assertTrue(rows[0]["is_limit_up"])


if __name__ == "__main__":
    unittest.main()
