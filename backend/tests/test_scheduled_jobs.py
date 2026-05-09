import unittest
from unittest.mock import patch

from app.db.database import get_connection, initialize_database
from app.services import scheduled_job_service


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


if __name__ == "__main__":
    unittest.main()
