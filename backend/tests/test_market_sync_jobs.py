import unittest
from inspect import signature
from threading import Event

from app.services import market_sync_jobs
from app.services import task_service
from app.services.market_service import update_market_data


class MarketSyncJobsTest(unittest.TestCase):
    def tearDown(self):
        market_sync_jobs.reset_sync_jobs_for_tests()
        from app.db.database import get_connection

        with get_connection() as conn:
            conn.execute("DELETE FROM task_runs WHERE task_type = 'sync_stock_daily'")

    def test_start_global_sync_job_records_progress_and_result(self):
        calls = []

        def fake_update(source=None, scope=None, limit=None, progress_callback=None):
            calls.append({"source": source, "scope": scope, "limit": limit})
            if progress_callback:
                progress_callback(42, "已同步 1/3 只股票")
            return {
                "source": source,
                "scope": scope,
                "stock_count": 3,
                "price_rows": 9,
                "failed_count": 0,
            }

        job = market_sync_jobs.start_full_market_sync(limit=3, run_inline=True, update_fn=fake_update)

        self.assertEqual(calls, [{"source": "akshare", "scope": "all", "limit": 3}])
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["progress"], 100)
        self.assertIsInstance(job["taskId"], int)
        self.assertEqual(job["result"]["stock_count"], 3)
        task = task_service.get_task_run(job["taskId"])
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["progress_percent"], 100)

        fetched = market_sync_jobs.get_sync_job(job["jobId"])
        self.assertEqual(fetched["status"], "completed")
        self.assertEqual(fetched["message"], "全市场股票池同步完成")

    def test_progress_callback_updates_running_job(self):
        seen = []

        def fake_update(**kwargs):
            progress_callback = kwargs["progress_callback"]
            progress_callback(31, "正在同步第 2/5 只股票")
            seen.append(market_sync_jobs.get_sync_job()["progress"])
            return {"stock_count": 5}

        job = market_sync_jobs.start_full_market_sync(limit=5, run_inline=True, update_fn=fake_update)

        self.assertEqual(seen, [31])
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["result"]["stock_count"], 5)

    def test_default_market_update_accepts_progress_callback(self):
        self.assertIn("progress_callback", signature(update_market_data).parameters)

    def test_start_global_sync_reuses_running_job(self):
        started = Event()
        release = Event()

        def blocking_update(**_kwargs):
            started.set()
            release.wait(timeout=2)
            return {"stock_count": 1}

        try:
            first = market_sync_jobs.start_full_market_sync(limit=5, run_inline=False, update_fn=blocking_update)
            started.wait(timeout=2)
            second = market_sync_jobs.start_full_market_sync(limit=10, run_inline=False, update_fn=blocking_update)
        finally:
            release.set()

        self.assertEqual(first["jobId"], second["jobId"])
        self.assertEqual(second["status"], "running")


if __name__ == "__main__":
    unittest.main()
