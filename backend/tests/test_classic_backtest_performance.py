import unittest
from unittest.mock import patch

from app.db.database import get_connection, initialize_database
from app.services.backtest_service import run_backtest


class ClassicBacktestPerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_classic_backtest_reuses_market_context_per_trade_date(self):
        with get_connection() as conn:
            strategy = conn.execute("SELECT id FROM strategies WHERE name = ?", ("价值动量策略",)).fetchone()
            self.assertIsNotNone(strategy)
            start = conn.execute("SELECT DISTINCT date FROM daily_prices ORDER BY date DESC LIMIT 170, 1").fetchone()["date"]
            end = conn.execute("SELECT MAX(date) AS date FROM daily_prices").fetchone()["date"]

        calls: list[str] = []

        def fake_market_regime(_stock_frames, trade_date=None, market_snapshot=None):
            calls.append(str(trade_date))
            return {
                "marketRegime": "RiskOn",
                "strategyPosture": {"ValueMomentumStrategy": "enabled"},
                "upStockRatio": 0.7,
                "limitUpCount": 80,
                "limitDownCount": 5,
            }

        def fake_signal(_strategy, _stock, _frame, _context, row_index=None):
            return {
                "signal_type": "classic_quant_candidate",
                "score": 82,
                "reason": "测试信号",
                "risk_reason": "",
                "risk_level": "low",
                "metadata": {
                    "strategyCandidate": {"suggestedAction": "观察"},
                },
            }

        result_id = None
        with (
            patch("app.services.backtest_service._resolve_stock_pool", return_value=["000001", "600519"]),
            patch("app.services.backtest_service.market_regime_model", side_effect=fake_market_regime),
            patch("app.services.backtest_service.evaluate_classic_strategy", side_effect=fake_signal),
        ):
            result = run_backtest(
                {
                    "strategy_id": strategy["id"],
                    "start_date": start,
                    "end_date": end,
                    "stock_pool": "all",
                }
            )
            result_id = result["id"]

        try:
            self.assertGreater(len(calls), 0)
            self.assertEqual(len(calls), len(set(calls)))
        finally:
            if result_id:
                with get_connection() as conn:
                    conn.execute("DELETE FROM backtest_results WHERE id = ?", (result_id,))
