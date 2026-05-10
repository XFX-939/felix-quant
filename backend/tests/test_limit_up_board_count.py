import unittest
from unittest.mock import patch

from app.db.database import get_connection, initialize_database
from app.services import market_data_service


class FakeLimitUpProvider:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_limit_up_pool(self, trade_date):
        self.trade_date = trade_date
        return [
            {
                "stock_code": "002281",
                "stock_name": "光迅科技",
                "industry": "通信",
                "close": 33.6,
                "change_pct": 10.0,
                "amount": 2600000000,
                "turnover_rate": 12.3,
                "market_value": 50000000000,
                "float_market_value": 42000000000,
                "is_limit_up": True,
                "is_broken_board": False,
                "first_limit_time": "09:30:00",
                "last_limit_time": "14:57:00",
                "open_board_count": 1,
                "seal_amount": 520000000,
                "seal_amount_ratio": 0.0124,
                "limit_up_type": "换手板",
                "board_count": 4,
                "raw_json": "{}",
            }
        ]


class LimitUpBoardCountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def tearDown(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM market_snapshots_daily WHERE trade_date = '2099-05-08' OR stock_code = '002281'")
            conn.execute("DELETE FROM daily_prices WHERE date = '2099-05-08' OR stock_code = '002281'")
            conn.execute("DELETE FROM stocks WHERE code = '002281'")

    def test_grouping_prefers_snapshot_board_count_over_history_fallback(self):
        rows = [
            {"code": "002281", "snapshotBoardCount": 4, "amount": 2600000000},
            {"code": "000001", "snapshotBoardCount": 0, "amount": 1200000000},
        ]

        with patch.object(market_data_service, "_board_heights", return_value={"002281": 1, "000001": 2}):
            grouped = market_data_service._group_limit_rows("2099-05-08", rows)

        self.assertIn(4, grouped)
        self.assertIn(2, grouped)
        self.assertEqual(grouped[4][0]["code"], "002281")
        self.assertEqual(grouped[2][0]["code"], "000001")

    def test_refresh_limit_up_pool_backfills_board_count_into_existing_snapshot(self):
        timestamp = "2099-05-08T15:00:00"
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO stocks (code, name, industry, market, created_at, updated_at)
                VALUES ('002281', '光迅科技', '未分类', 'SZ', ?, ?)
                """,
                (timestamp, timestamp),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO market_snapshots_daily (
                    trade_date, stock_code, stock_name, market, industry, open, high, low, close, pre_close,
                    change_pct, volume, amount, turnover_rate, market_value, float_market_value,
                    limit_up_price, limit_down_price, is_limit_up, is_limit_down, is_suspended, is_st,
                    is_broken_board, first_limit_time, last_limit_time, open_board_count, seal_amount,
                    seal_amount_ratio, limit_up_type, board_count, is_new_high, raw_json, created_at, updated_at
                )
                VALUES (
                    '2099-05-08', '002281', '光迅科技', 'SZ', '未分类', 30, 33.6, 30, 33.6, 30.55,
                    10, 1000000, 2000000000, 8, 50000000000, 42000000000,
                    33.6, 27.5, 1, 0, 0, 0,
                    0, NULL, NULL, 0, 0,
                    0, '未知', 0, 0, '{}', ?, ?
                )
                """,
                (timestamp, timestamp),
            )

        with patch.object(market_data_service, "AkshareDataProvider", FakeLimitUpProvider):
            result = market_data_service.refresh_limit_up_pool("2099-05-08")

        self.assertEqual(result["updatedCount"], 1)
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT industry, board_count, first_limit_time, last_limit_time, open_board_count, seal_amount
                FROM market_snapshots_daily
                WHERE trade_date = '2099-05-08' AND stock_code = '002281'
                """
            ).fetchone()
        self.assertEqual(row["industry"], "通信")
        self.assertEqual(row["board_count"], 4)
        self.assertEqual(row["first_limit_time"], "09:30:00")
        self.assertEqual(row["last_limit_time"], "14:57:00")
        self.assertEqual(row["open_board_count"], 1)
        self.assertEqual(row["seal_amount"], 520000000)


if __name__ == "__main__":
    unittest.main()
