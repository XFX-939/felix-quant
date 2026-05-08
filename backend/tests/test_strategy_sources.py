import json
import unittest

from app.db.database import get_connection, initialize_database, now_iso
from app.services.strategy_source_service import (
    get_strategy_source,
    list_strategy_sources,
    summarize_strategy_sources,
)


class StrategySourceServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_every_strategy_has_traceable_source(self):
        with get_connection() as conn:
            strategy_names = [
                row["name"]
                for row in conn.execute("SELECT name FROM strategies ORDER BY id").fetchall()
            ]

        sources = {item["strategyName"]: item for item in list_strategy_sources()}

        self.assertTrue(strategy_names)
        self.assertTrue(set(strategy_names).issubset(sources.keys()))
        for name in strategy_names:
            source = sources[name]
            self.assertIn(source["sourceType"], {
                "academic_paper",
                "broker_research",
                "quant_firm_research",
                "public_blog",
                "book",
                "open_source",
                "self_developed",
                "inspired_by",
                "unknown",
            })
            self.assertTrue(source["sourceSummary"])
            self.assertTrue(source["originalIdea"])
            self.assertTrue(source["localAdaptation"])
            self.assertIn(source["confidenceLevel"], {"高", "中", "低"})

    def test_self_developed_hotspot_source_does_not_claim_institution_backing(self):
        source = get_strategy_source("市场热点候选策略")

        self.assertEqual(source["sourceType"], "self_developed")
        self.assertIn("自研", source["sourceName"])
        combined_text = " ".join(
            [
                source.get("sourceName", ""),
                source.get("sourceTitle", "") or "",
                source.get("sourceSummary", ""),
                source.get("originalIdea", ""),
            ]
        )
        self.assertNotIn("幻方", combined_text)
        self.assertNotIn("中信", combined_text)
        self.assertNotIn("Two Sigma", combined_text)

    def test_backtest_sample_insufficient_caps_confidence(self):
        strategy_name = "unit_test_source_confidence"
        timestamp = now_iso()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
                VALUES (?, 'source confidence test', '趋势', '{}', 1, ?, ?)
                """,
                (strategy_name, timestamp, timestamp),
            )
            strategy_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO backtest_results (
                    strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                    sharpe, win_rate, trade_count, result_json, created_at
                )
                VALUES (?, '2099-01-01', '2099-01-20', 0.1, 1.2, 0.02, 1.1, 0.7, 5, ?, ?)
                """,
                (
                    strategy_id,
                    json.dumps({"equity_curve": [], "trades": []}, ensure_ascii=False),
                    timestamp,
                ),
            )
        try:
            source = get_strategy_source(strategy_name)
            self.assertEqual(source["sourceType"], "self_developed")
            self.assertNotEqual(source["confidenceLevel"], "高")
            self.assertEqual(source["backtestValidity"], "样本不足")
            self.assertFalse(source["isVerifiedByBacktest"])
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM strategy_sources WHERE strategy_name = ?", (strategy_name,))
                conn.execute("DELETE FROM backtest_results WHERE strategy_id = ?", (strategy_id,))
                conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))

    def test_source_summary_counts_unverified_and_self_developed(self):
        summary = summarize_strategy_sources()

        self.assertGreaterEqual(summary["selfDevelopedCount"], 1)
        self.assertIn("lowConfidenceCount", summary)
        self.assertIn("insufficientBacktestCount", summary)

