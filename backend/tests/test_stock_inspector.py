import unittest
from datetime import date, timedelta
from unittest.mock import patch

from app.db.database import get_connection, initialize_database, now_iso
from app.services import stock_inspector_service
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

    def test_report_repairs_short_history_and_ignores_suspect_list_date(self):
        code = "TST261"
        trade_date = date(2099, 5, 8)
        timestamp = now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO stocks (
                    code, name, industry, market, list_date, is_st, is_suspended,
                    float_market_cap, created_at, updated_at
                )
                VALUES (?, '拓维信息测试', '计算机', 'SZ', ?, 0, 0, 8000000000, ?, ?)
                """,
                (code, trade_date.isoformat(), timestamp, timestamp),
            )
            conn.execute(
                """
                INSERT INTO daily_prices
                    (stock_code, date, open, high, low, close, volume, amount, pct_change)
                VALUES (?, ?, 35, 36, 34, 35, 1000000, 35000000, -4.9)
                """,
                (code, trade_date.isoformat()),
            )
        history = _history_rows(code, trade_date, 130)
        try:
            with patch.object(stock_inspector_service, "_fetch_history_prices", return_value=history, create=True):
                report = get_stock_inspection_report(code, force=True)

            self.assertNotEqual(report["researchRating"], "无法评级")
            self.assertNotEqual(report["dataConfidence"], "低")
            self.assertFalse(report["rawFactors"]["hardRiskTriggered"])
            self.assertIsNone(report["rawFactors"]["listedDays"])
            self.assertIsNotNone(report["targetPriceRange"]["mid"])
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM stock_diagnosis_reports WHERE code = ?", (code,))
                conn.execute("DELETE FROM daily_prices WHERE stock_code = ?", (code,))
                conn.execute("DELETE FROM stocks WHERE code = ?", (code,))


def _history_rows(code: str, end_date: date, count: int) -> list[dict]:
    rows: list[dict] = []
    for index in range(count):
        day = end_date - timedelta(days=count - index - 1)
        close = 20 + index * 0.12
        previous_close = 20 + max(index - 1, 0) * 0.12
        pct_change = (close / previous_close - 1) * 100 if index else 0
        rows.append(
            {
                "stock_code": code,
                "date": day.isoformat(),
                "open": round(close * 0.99, 2),
                "high": round(close * 1.02, 2),
                "low": round(close * 0.98, 2),
                "close": round(close, 2),
                "volume": 1000000 + index * 1000,
                "amount": round((1000000 + index * 1000) * close, 2),
                "pct_change": round(pct_change, 2),
            }
        )
    return rows


if __name__ == "__main__":
    unittest.main()
