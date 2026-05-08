import unittest

from app.services.backtest_service import check_backtest_validity


class BacktestValidityTest(unittest.TestCase):
    def test_trade_count_under_30_is_sample_insufficient(self):
        validity = check_backtest_validity(
            {
                "start_date": "2026-01-01",
                "end_date": "2026-03-01",
                "trade_count": 1,
                "result_json": {"fee_rate": 0.0003, "slippage": 0.0005},
            }
        )

        self.assertEqual(validity["validityLevel"], "样本不足")
        self.assertEqual(validity["sampleSizeLevel"], "样本不足")
        self.assertFalse(validity["usableForDecision"])
        self.assertFalse(validity["usableForStrategyJudgement"])
        self.assertTrue(any("交易次数不足 30" in item for item in validity["validityWarnings"]))
        self.assertIn("功能验证", validity["conclusion"])

    def test_missing_slippage_and_short_range_add_warnings(self):
        validity = check_backtest_validity(
            {
                "start_date": "2026-01-01",
                "end_date": "2026-06-01",
                "trade_count": 40,
                "result_json": {"fee_rate": 0.0003},
            }
        )

        self.assertEqual(validity["validityLevel"], "区间不足")
        self.assertTrue(any("回测区间不足一年" in item for item in validity["validityWarnings"]))
        self.assertTrue(any("未计入滑点" in item for item in validity["validityWarnings"]))

    def test_sample_pool_returns_actionable_repair_suggestions(self):
        validity = check_backtest_validity(
            {
                "start_date": "2025-01-01",
                "end_date": "2026-01-01",
                "trade_count": 80,
                "result_json": {
                    "stock_pool": "sample",
                    "stock_count": 10,
                    "fee_rate": 0.0003,
                    "slippage": 0.001,
                    "st_suspension_delist_handled": False,
                    "financial_announcement_lag_handled": False,
                    "data_coverage_ratio": 0.72,
                },
            }
        )

        self.assertEqual(validity["validityLevel"], "仅功能验证")
        self.assertEqual(validity["stockPoolSize"], 10)
        self.assertAlmostEqual(validity["dataCoverageRatio"], 0.72)
        self.assertTrue(validity["feeIncluded"])
        self.assertTrue(validity["slippageIncluded"])
        self.assertTrue(validity["survivorBiasRisk"])
        self.assertTrue(validity["forwardBiasRisk"])
        self.assertTrue(any("切换为全市场股票池" in item for item in validity["repairSuggestions"]))
        self.assertTrue(any("补齐历史行情数据" in item for item in validity["repairSuggestions"]))


if __name__ == "__main__":
    unittest.main()
