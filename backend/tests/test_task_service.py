import unittest

from app.db.database import get_connection, initialize_database
from app.services import task_service


class TaskServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def tearDown(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM task_runs WHERE task_type LIKE 'unit_test_%'")
            conn.execute("DELETE FROM failed_sync_records WHERE task_type LIKE 'unit_test_%'")

    def test_task_run_tracks_progress_and_duration(self):
        task = task_service.create_task_run("unit_test_pipeline", "2099-01-01", total_count=10)

        task_service.update_task_run(
            task["id"],
            status="running",
            current_stage="sync_target_stock_daily",
            processed_count=4,
            success_count=3,
            failed_count=1,
            retry_count=2,
        )
        running = task_service.get_task_run(task["id"])

        self.assertEqual(running["status"], "running")
        self.assertEqual(running["current_stage"], "sync_target_stock_daily")
        self.assertEqual(running["progress_percent"], 40)
        self.assertEqual(running["retry_count"], 2)

        task_service.finish_task_run(task["id"], status="partial_success", summary={"ok": True})
        finished = task_service.get_task_run(task["id"])

        self.assertEqual(finished["status"], "partial_success")
        self.assertGreaterEqual(finished["duration_ms"], 0)
        self.assertEqual(finished["summary_json"]["ok"], True)

    def test_running_task_prevents_duplicate_same_type_and_date(self):
        first = task_service.create_task_run("unit_test_pipeline", "2099-01-02")

        duplicate = task_service.find_running_task("unit_test_pipeline", "2099-01-02")

        self.assertEqual(duplicate["id"], first["id"])

    def test_failed_sync_record_upserts_and_recovers(self):
        task_service.record_failed_sync(
            trade_date="2099-01-03",
            code="000755",
            name="山西高速",
            task_type="unit_test_stock_daily",
            data_type="stock_daily",
            status="failed",
            retry_count=3,
            max_retries=3,
            error_message="Max retries exceeded",
            raw_context={"source": "akshare"},
        )
        task_service.record_failed_sync(
            trade_date="2099-01-03",
            code="000755",
            name="山西高速",
            task_type="unit_test_stock_daily",
            data_type="stock_daily",
            status="failed",
            retry_count=3,
            max_retries=3,
            error_message="Second error",
            raw_context={"source": "sina"},
        )

        failed = task_service.list_failed_sync_records(task_type="unit_test_stock_daily")

        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["error_message"], "Second error")
        self.assertEqual(failed[0]["retry_count"], 3)
        self.assertEqual(failed[0]["raw_context_json"]["source"], "sina")

        task_service.mark_sync_recovered("2099-01-03", "000755", "unit_test_stock_daily", "stock_daily")
        recovered = task_service.list_failed_sync_records(task_type="unit_test_stock_daily", status="recovered")

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "recovered")


if __name__ == "__main__":
    unittest.main()
