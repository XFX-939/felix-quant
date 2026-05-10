import unittest
from datetime import date
from unittest.mock import patch

from app.db.database import get_connection, initialize_database
from app.services import scheduled_job_service


class WeekendDate(date):
    @classmethod
    def today(cls):
        return cls(2099, 5, 10)


class ScheduledJobServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def tearDown(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM job_runs WHERE data_date LIKE '2099-%' OR trigger_type = 'unit_test'")
            conn.execute("DELETE FROM dashboard_snapshots WHERE data_date LIKE '2099-%'")
            conn.execute("DELETE FROM data_sync_status WHERE data_date LIKE '2099-%'")

    def test_scheduled_jobs_are_seeded_with_three_refresh_windows(self):
        scheduled_job_service.ensure_scheduled_jobs()

        jobs = scheduled_job_service.list_scheduled_jobs()
        names = {job["job_name"] for job in jobs}

        self.assertIn("morning_prewarm_job", names)
        self.assertIn("midday_refresh_job", names)
        self.assertIn("after_close_refresh_job", names)
        self.assertEqual({job["timezone"] for job in jobs}, {scheduled_job_service.JOB_TIMEZONE})

    def test_running_job_is_reused_instead_of_starting_duplicate(self):
        with (
            patch.object(scheduled_job_service, "target_trade_date", return_value="2099-05-09"),
            patch.object(scheduled_job_service._executor, "submit") as submit,
        ):
            first = scheduled_job_service.start_job("after_close_refresh_job", trigger_type="unit_test")
            second = scheduled_job_service.start_job("after_close_refresh_job", trigger_type="unit_test")

        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["reused"])
        submit.assert_called_once()

    def test_dashboard_latest_prefers_persisted_snapshot(self):
        summary = {"last_data_date": "2099-05-09", "market_regime": {"marketRegime": "RiskOn"}}
        with patch.object(scheduled_job_service, "dashboard_summary", return_value=summary):
            scheduled_job_service.build_dashboard_snapshot("after_close", data_date="2099-05-09")

        latest = scheduled_job_service.dashboard_latest_or_live()

        self.assertTrue(latest["snapshot_meta"]["fromDatabaseSnapshot"])
        self.assertEqual(latest["snapshot_meta"]["dataDate"], "2099-05-09")
        self.assertEqual(latest["snapshot_meta"]["snapshotType"], "after_close")

    def test_non_trading_day_generates_snapshot_from_cached_previous_trade_date(self):
        definition = scheduled_job_service._definition_for_job("after_close_refresh_job")
        self.assertIsNotNone(definition)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO stocks (code, name, industry, market, created_at, updated_at)
                VALUES ('T2099', '测试股票', '测试行业', '主板', '2099-05-08T15:00:00', '2099-05-08T15:00:00')
                """
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO market_snapshots_daily (
                    trade_date, stock_code, stock_name, open, high, low, close, pre_close,
                    change_pct, volume, amount, turnover_rate, is_limit_up, is_limit_down,
                    industry, market, created_at, updated_at
                )
                VALUES (
                    '2099-05-08', 'T2099', '测试股票', 10, 11, 9.8, 10.8, 10,
                    8, 10000, 1000000, 3, 0, 0, '测试行业', '主板',
                    '2099-05-08T15:00:00', '2099-05-08T15:00:00'
                )
                """
            )
        run = scheduled_job_service._create_job_run(definition, "unit_test", "2099-05-08")
        with (
            patch.object(scheduled_job_service, "date", WeekendDate),
            patch.object(scheduled_job_service, "target_trade_date", return_value="2099-05-08"),
            patch.object(scheduled_job_service, "run_strategies", return_value={"strategies_run": 2, "signals_created": 3}),
            patch.object(scheduled_job_service, "refresh_strategy_performance", return_value={"periodsWritten": 4, "failedCount": 0}),
            patch.object(scheduled_job_service, "dashboard_summary", return_value={"last_data_date": "2099-05-08", "market_regime": {"marketRegime": "Choppy"}}),
        ):
            scheduled_job_service._run_job(run["id"], definition, force=False)

        finished = scheduled_job_service.get_job_run(run["id"])
        snapshot = scheduled_job_service.latest_dashboard_snapshot()

        self.assertEqual(finished["status"], "success")
        self.assertIn("non_trading_cache_refresh", finished["result_summary"]["job"])
        self.assertEqual(snapshot["data_date"], "2099-05-08")
        self.assertEqual(snapshot["snapshot_type"], "after_close")


if __name__ == "__main__":
    unittest.main()
