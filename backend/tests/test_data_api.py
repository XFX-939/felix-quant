import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api import data as data_api


class DataApiTest(unittest.TestCase):
    def test_update_is_rejected_while_full_market_sync_is_running(self):
        with (
            patch.object(data_api, "get_sync_job", return_value={"status": "running", "message": "正在同步日线"}),
            patch.object(data_api, "update_market_data") as update_market_data,
            patch.object(data_api, "run_strategies") as run_strategies,
        ):
            with self.assertRaises(HTTPException) as context:
                data_api.update_data_and_run()

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("全市场同步正在进行", context.exception.detail)
        update_market_data.assert_not_called()
        run_strategies.assert_not_called()


if __name__ == "__main__":
    unittest.main()
