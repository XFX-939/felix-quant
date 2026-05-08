import unittest

from app.db.database import get_connection, initialize_database
from app.services.stock_inspector_service import determine_research_rating, estimate_target_price_range, get_stock_inspection_report


class StockInspectorRatingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def tearDown(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM stock_diagnosis_reports WHERE code = '000001'")

    def test_high_risk_downtrend_is_sell_even_with_high_score(self):
        rating = determine_research_rating(
            overall_score=86,
            risk_level="高",
            data_confidence="高",
            trend_status="下行",
            market_regime="RiskOn",
            hard_risk_triggered=False,
            is_st=False,
            is_suspended=False,
            listed_days=180,
            technical_score=82,
            fundamental_score=78,
            volatility_60=0.28,
            mainline_match=False,
        )

        self.assertEqual(rating["researchRating"], "卖出")
        self.assertTrue(any("高风险" in reason for reason in rating["ratingReasons"]))

    def test_low_data_confidence_caps_rating_at_hold(self):
        rating = determine_research_rating(
            overall_score=94,
            risk_level="低",
            data_confidence="低",
            trend_status="上行",
            market_regime="RiskOn",
            hard_risk_triggered=False,
            is_st=False,
            is_suspended=False,
            listed_days=260,
            technical_score=92,
            fundamental_score=None,
            volatility_60=0.18,
            mainline_match=True,
        )

        self.assertEqual(rating["researchRating"], "持有")
        self.assertTrue(any("数据可信度低" in reason for reason in rating["ratingReasons"]))

    def test_low_data_confidence_with_non_low_risk_is_unrated(self):
        rating = determine_research_rating(
            overall_score=70,
            risk_level="中",
            data_confidence="低",
            trend_status="震荡",
            market_regime="Choppy",
            hard_risk_triggered=False,
            is_st=False,
            is_suspended=False,
            listed_days=120,
            technical_score=65,
            fundamental_score=None,
            volatility_60=0.32,
            mainline_match=False,
        )

        self.assertEqual(rating["researchRating"], "无法评级")

    def test_panic_market_caps_rating_at_hold(self):
        rating = determine_research_rating(
            overall_score=96,
            risk_level="低",
            data_confidence="高",
            trend_status="上行",
            market_regime="Panic",
            hard_risk_triggered=False,
            is_st=False,
            is_suspended=False,
            listed_days=500,
            technical_score=94,
            fundamental_score=90,
            volatility_60=0.16,
            mainline_match=True,
        )

        self.assertEqual(rating["researchRating"], "持有")

    def test_risk_on_high_quality_stock_can_be_buy(self):
        rating = determine_research_rating(
            overall_score=88,
            risk_level="低",
            data_confidence="高",
            trend_status="上行",
            market_regime="RiskOn",
            hard_risk_triggered=False,
            is_st=False,
            is_suspended=False,
            listed_days=700,
            technical_score=90,
            fundamental_score=86,
            volatility_60=0.22,
            mainline_match=True,
        )

        self.assertEqual(rating["researchRating"], "买入")
        self.assertTrue(any("RiskOn" in reason for reason in rating["ratingReasons"]))

    def test_target_price_range_is_not_fabricated_when_data_is_insufficient(self):
        target = estimate_target_price_range([], None)

        self.assertIsNone(target["low"])
        self.assertEqual(target["confidence"], "低")
        self.assertIn("数据不足", target["method"])

    def test_report_is_cached_by_code_and_trade_date(self):
        first = get_stock_inspection_report("000001", force=True)
        second = get_stock_inspection_report("000001")

        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM stock_diagnosis_reports WHERE code = ? AND trade_date = ?",
                ("000001", first["tradeDate"]),
            ).fetchone()["c"]

        self.assertEqual(first["code"], second["code"])
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
