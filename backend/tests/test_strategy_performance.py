import json
import unittest
from unittest.mock import patch

from app.db.database import get_connection, initialize_database, now_iso
from app.services import strategy_performance_service


class StrategyPerformanceServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.strategy_name = "unit_test_performance_strategy"
        timestamp = now_iso()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
                VALUES (?, 'unit test', '趋势', '{}', 1, ?, ?)
                """,
                (self.strategy_name, timestamp, timestamp),
            )
            self.strategy_id = cursor.lastrowid
            equity_curve = [
                {"date": f"2099-01-{day:02d}", "value": 100000 + day * 1000, "return": 0.01}
                for day in range(1, 32)
            ]
            trades = [
                {
                    "date": f"2099-01-{day:02d}",
                    "stock_code": "000001",
                    "return": 0.01 if day % 2 else -0.004,
                    "holding_days": 2,
                }
                for day in range(1, 12)
            ]
            conn.execute(
                """
                INSERT INTO backtest_results (
                    strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                    sharpe, win_rate, trade_count, result_json, created_at
                )
                VALUES (?, '2099-01-01', '2099-01-31', 0.31, 2.0, 0.02, 1.2, 0.55, ?, ?, ?)
                """,
                (
                    self.strategy_id,
                    len(trades),
                    json.dumps(
                        {
                            "initial_cash": 100000,
                            "fee_rate": 0.0003,
                            "slippage": 0.0005,
                            "avg_holding_days": 2,
                            "equity_curve": equity_curve,
                            "drawdown_curve": [],
                            "trades": trades,
                        },
                        ensure_ascii=False,
                    ),
                    timestamp,
                ),
            )

    def tearDown(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM strategy_performance_summary WHERE strategy_name = ?", (self.strategy_name,))
            conn.execute("DELETE FROM strategy_nav_daily WHERE strategy_name = ?", (self.strategy_name,))
            conn.execute("DELETE FROM strategy_trade_records WHERE strategy_name = ?", (self.strategy_name,))
            conn.execute("DELETE FROM backtest_results WHERE strategy_id = ?", (self.strategy_id,))
            conn.execute("DELETE FROM strategies WHERE id = ?", (self.strategy_id,))

    def test_refresh_generates_nav_and_period_summary_from_backtest(self):
        result = strategy_performance_service.refresh_strategy_performance(force=True)

        self.assertGreaterEqual(result["strategyCount"], 1)
        with get_connection() as conn:
            nav_count = conn.execute(
                "SELECT COUNT(*) AS c FROM strategy_nav_daily WHERE strategy_name = ?",
                (self.strategy_name,),
            ).fetchone()["c"]
            summary = conn.execute(
                """
                SELECT *
                FROM strategy_performance_summary
                WHERE strategy_name = ? AND period = '1M'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (self.strategy_name,),
            ).fetchone()

        self.assertEqual(nav_count, 31)
        self.assertIsNotNone(summary)
        self.assertGreater(summary["return_rate"], 0)
        self.assertEqual(summary["validity_level"], "样本不足")

    def test_summary_api_shape_contains_all_periods(self):
        strategy_performance_service.refresh_strategy_performance(force=True)

        summary = strategy_performance_service.get_strategy_performance_summary()
        item = next(row for row in summary["strategies"] if row["strategyName"] == self.strategy_name)

        self.assertIn("1M", item["periods"])
        self.assertIn("3M", item["periods"])
        self.assertEqual(item["periods"]["1M"]["validityLevel"], "样本不足")

    def test_overview_excludes_sample_insufficient_flat_nav_from_best_strategy(self):
        flat_name = f"{self.strategy_name}_flat"
        timestamp = now_iso()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
                VALUES (?, 'flat nav test', '趋势', '{}', 1, ?, ?)
                """,
                (flat_name, timestamp, timestamp),
            )
            flat_strategy_id = cursor.lastrowid
            equity_curve = [
                {"date": f"2099-02-{day:02d}", "value": 100000, "return": 0.0}
                for day in range(1, 22)
            ]
            conn.execute(
                """
                INSERT INTO backtest_results (
                    strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                    sharpe, win_rate, trade_count, result_json, created_at
                )
                VALUES (?, '2099-02-01', '2099-02-21', 0, 0, 0, 0, 0, 0, ?, ?)
                """,
                (
                    flat_strategy_id,
                    json.dumps(
                        {
                            "initial_cash": 100000,
                            "fee_rate": 0.0003,
                            "slippage": 0.0005,
                            "equity_curve": equity_curve,
                            "trades": [],
                        },
                        ensure_ascii=False,
                    ),
                    timestamp,
                ),
            )
        try:
            strategy_performance_service.refresh_strategy_performance(force=True)

            summary = strategy_performance_service.get_strategy_performance_summary(strategy_names=[flat_name])

            self.assertIsNone(summary["overview"]["best1M"])
            self.assertEqual(summary["strategies"][0]["periods"]["1M"]["validityLevel"], "样本不足")
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM strategy_performance_summary WHERE strategy_name = ?", (flat_name,))
                conn.execute("DELETE FROM strategy_nav_daily WHERE strategy_name = ?", (flat_name,))
                conn.execute("DELETE FROM strategy_trade_records WHERE strategy_name = ?", (flat_name,))
                conn.execute("DELETE FROM backtest_results WHERE strategy_id = ?", (flat_strategy_id,))
                conn.execute("DELETE FROM strategies WHERE id = ?", (flat_strategy_id,))

    def test_truncated_backtest_trade_details_are_marked_data_insufficient(self):
        truncated_name = f"{self.strategy_name}_truncated"
        timestamp = now_iso()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
                VALUES (?, 'truncated trade test', '趋势', '{}', 1, ?, ?)
                """,
                (truncated_name, timestamp, timestamp),
            )
            truncated_strategy_id = cursor.lastrowid
            equity_curve = [
                {"date": f"2099-03-{day:02d}", "value": 100000 + day * 500, "return": 0.005}
                for day in range(1, 32)
            ]
            trades = [
                {"date": f"2099-03-{day:02d}", "stock_code": "000001", "return": 0.01, "holding_days": 1}
                for day in range(1, 6)
            ]
            conn.execute(
                """
                INSERT INTO backtest_results (
                    strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                    sharpe, win_rate, trade_count, result_json, created_at
                )
                VALUES (?, '2099-03-01', '2099-03-31', 0.15, 1.0, 0.01, 1, 0.6, 40, ?, ?)
                """,
                (
                    truncated_strategy_id,
                    json.dumps(
                        {
                            "initial_cash": 100000,
                            "fee_rate": 0.0003,
                            "slippage": 0.0005,
                            "equity_curve": equity_curve,
                            "trades": trades,
                        },
                        ensure_ascii=False,
                    ),
                    timestamp,
                ),
            )
        try:
            strategy_performance_service.refresh_strategy_performance(force=True)

            summary = strategy_performance_service.get_strategy_performance_summary(strategy_names=[truncated_name])
            one_month = summary["strategies"][0]["periods"]["1M"]

            self.assertEqual(one_month["validityLevel"], "数据不足")
            self.assertTrue(any("交易明细不完整" in warning for warning in one_month["warnings"]))
            self.assertIsNone(summary["overview"]["best1M"])
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM strategy_performance_summary WHERE strategy_name = ?", (truncated_name,))
                conn.execute("DELETE FROM strategy_nav_daily WHERE strategy_name = ?", (truncated_name,))
                conn.execute("DELETE FROM strategy_trade_records WHERE strategy_name = ?", (truncated_name,))
                conn.execute("DELETE FROM backtest_results WHERE strategy_id = ?", (truncated_strategy_id,))
                conn.execute("DELETE FROM strategies WHERE id = ?", (truncated_strategy_id,))

    def test_missing_backtest_nav_generation_uses_bounded_candidate_pool(self):
        no_backtest_name = f"{self.strategy_name}_no_backtest"
        timestamp = now_iso()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
                VALUES (?, 'no backtest test', '经典多因子', ?, 1, ?, ?)
                """,
                (
                    no_backtest_name,
                    json.dumps({"strategy_class": "ValueMomentumStrategy"}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            no_backtest_strategy_id = cursor.lastrowid

        seen_payloads = []

        def fake_run_backtest(payload):
            seen_payloads.append(payload)
            return {
                "strategy_name": no_backtest_name,
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                "result_json": {"initial_cash": 100000, "equity_curve": [], "trades": []},
            }

        try:
            with patch("app.services.backtest_service.run_backtest", side_effect=fake_run_backtest):
                strategy_performance_service.generate_strategy_nav_from_backtests(
                    strategy_name=no_backtest_name,
                    force=False,
                )

            self.assertEqual(seen_payloads[0]["stock_pool"], "today_candidates_only")
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM strategy_performance_summary WHERE strategy_name = ?", (no_backtest_name,))
                conn.execute("DELETE FROM strategy_nav_daily WHERE strategy_name = ?", (no_backtest_name,))
                conn.execute("DELETE FROM strategy_trade_records WHERE strategy_name = ?", (no_backtest_name,))
                conn.execute("DELETE FROM backtest_results WHERE strategy_id = ?", (no_backtest_strategy_id,))
                conn.execute("DELETE FROM strategies WHERE id = ?", (no_backtest_strategy_id,))


if __name__ == "__main__":
    unittest.main()
