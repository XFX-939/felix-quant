import unittest

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


if __name__ == "__main__":
    unittest.main()
