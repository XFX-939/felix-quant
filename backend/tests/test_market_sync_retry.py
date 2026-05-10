import unittest
from datetime import date, timedelta

from app.db.database import get_connection, initialize_database, now_iso
from app.services import market_service


class FailingProvider:
    def __init__(self):
        self.attempts = 0

    def fetch_daily_prices(self, code, start_date, end_date, adjust):
        self.attempts += 1
        raise ConnectionError("Remote source timed out")


class EventuallySuccessfulProvider:
    def __init__(self):
        self.attempts = 0

    def fetch_daily_prices(self, code, start_date, end_date, adjust):
        self.attempts += 1
        if self.attempts < 3:
            raise ConnectionError("temporary timeout")
        return [{"stock_code": code, "date": "2099-01-01"}]


class MarketSyncRetryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_daily_fetch_retries_three_times_with_backoff_then_raises(self):
        provider = FailingProvider()
        slept = []

        with self.assertRaises(ConnectionError):
            market_service._fetch_daily_prices_with_retry(
                provider,
                code="000755",
                start_date="20990101",
                end_date="20990101",
                adjust="qfq",
                sleep_fn=slept.append,
            )

        self.assertEqual(provider.attempts, 4)
        self.assertEqual(slept, [2, 5, 10])

    def test_daily_fetch_returns_after_successful_retry(self):
        provider = EventuallySuccessfulProvider()
        slept = []

        prices, retry_count = market_service._fetch_daily_prices_with_retry(
            provider,
            code="000755",
            start_date="20990101",
            end_date="20990101",
            adjust="qfq",
            sleep_fn=slept.append,
        )

        self.assertEqual(prices, [{"stock_code": "000755", "date": "2099-01-01"}])
        self.assertEqual(retry_count, 2)
        self.assertEqual(slept, [2, 5])

    def test_failure_rate_guard_waits_for_minimum_sample(self):
        self.assertIsNone(market_service._failure_rate_stop_reason(processed_count=3, failed_count=3, total_count=100))

    def test_failure_rate_guard_stops_when_threshold_exceeded(self):
        reason = market_service._failure_rate_stop_reason(processed_count=20, failed_count=6, total_count=100)

        self.assertIsNotNone(reason)
        self.assertIn("超过 25% 阈值", reason)

    def test_daily_sync_window_backfills_when_latest_date_exists_but_history_is_short(self):
        code = "TST001"
        end = date(2099, 12, 31)
        timestamp = now_iso()
        original_history_days = market_service.AKSHARE_HISTORY_DAYS
        market_service.AKSHARE_HISTORY_DAYS = 250
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO stocks (code, name, industry, market, created_at, updated_at)
                    VALUES (?, '同步窗口测试', '测试', 'SZ', ?, ?)
                    ON CONFLICT(code) DO UPDATE SET updated_at = excluded.updated_at
                    """,
                    (code, timestamp, timestamp),
                )
                for offset in range(60):
                    day = end - timedelta(days=offset)
                    if day.weekday() >= 5:
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO daily_prices
                            (stock_code, date, open, high, low, close, volume, amount, pct_change)
                        VALUES (?, ?, 10, 11, 9, 10, 1000, 10000, 0)
                        """,
                        (code, day.isoformat()),
                    )
                conn.execute(
                    """
                    INSERT INTO stock_sync_state (code, last_daily_date, status, updated_at)
                    VALUES (?, ?, 'success', ?)
                    ON CONFLICT(code) DO UPDATE SET last_daily_date = excluded.last_daily_date
                    """,
                    (code, end.isoformat(), timestamp),
                )

            window = market_service._daily_sync_window(code, end)

            expected_start = (end - timedelta(days=450)).strftime("%Y%m%d")
            self.assertEqual(window, (expected_start, end.strftime("%Y%m%d")))
        finally:
            market_service.AKSHARE_HISTORY_DAYS = original_history_days
            with get_connection() as conn:
                conn.execute("DELETE FROM stock_sync_state WHERE code = ?", (code,))
                conn.execute("DELETE FROM daily_prices WHERE stock_code = ?", (code,))
                conn.execute("DELETE FROM stocks WHERE code = ?", (code,))


if __name__ == "__main__":
    unittest.main()
