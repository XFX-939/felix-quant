import unittest

import pandas as pd

from app.services.classic_quant import market_regime_model
from app.services.decision_engine import data_coverage_panel, detect_market_themes
from app.services.hotspot_data_provider import get_market_snapshot


def _frame(code: str, pct_change: float) -> dict:
    closes = [10 + index * 0.01 for index in range(80)]
    return {
        "stock": {"code": code, "name": code, "industry": "电子", "market": "SZ"},
        "frame": pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=80, freq="D"),
                "open": closes,
                "high": [value * 1.01 for value in closes],
                "low": [value * 0.99 for value in closes],
                "close": closes,
                "volume": [10000000 for _ in closes],
                "amount": [120000000 for _ in closes],
                "pct_change": [pct_change for _ in closes],
                "ma20": pd.Series(closes).rolling(20).mean(),
                "ma60": pd.Series(closes).rolling(60).mean(),
                "high20": pd.Series([value * 1.01 for value in closes]).rolling(20).max(),
                "ret20": pd.Series(closes) / pd.Series(closes).shift(20) - 1,
                "ret60": pd.Series(closes) / pd.Series(closes).shift(60) - 1,
                "volatility_60": [0.2 for _ in closes],
                "max_drawdown_60": [0.1 for _ in closes],
            }
        ),
    }


class MarketSnapshotProviderTest(unittest.TestCase):
    def test_20260508_snapshot_uses_public_close_values(self):
        snapshot = get_market_snapshot("2026-05-08")
        data = snapshot["data"]

        self.assertTrue(snapshot["ready"])
        self.assertEqual(data["shIndexClose"], 4179.95)
        self.assertEqual(data["shIndexPctChg"], 0.0)
        self.assertEqual(data["szIndexClose"], 15563.8)
        self.assertEqual(data["szIndexPctChg"], -0.5)
        self.assertEqual(data["cybIndexClose"], 3796.13)
        self.assertEqual(data["cybIndexPctChg"], -0.96)
        self.assertEqual(data["kc50Close"], 1640.46)
        self.assertEqual(data["kc50PctChg"], -2.29)
        self.assertEqual(data["limitUpCount"], 112)
        self.assertEqual(data["themes"][0]["name"], "商业航天")

    def test_market_regime_exposes_index_close_values(self):
        snapshot = get_market_snapshot("2026-05-08")["data"]
        context = market_regime_model(
            [_frame("600001", 0.8), _frame("000001", 1.1), _frame("300001", 1.2), _frame("688001", 0.7)],
            "2026-05-08",
            market_snapshot=snapshot,
        )

        self.assertEqual(context["shIndexClose"], 4179.95)
        self.assertEqual(context["szIndexClose"], 15563.8)
        self.assertEqual(context["cybIndexClose"], 3796.13)
        self.assertEqual(context["kc50Close"], 1640.46)
        self.assertEqual(context["shIndexPctChg"], 0.0)
        self.assertEqual(context["szIndexPctChg"], -0.5)

    def test_manual_snapshot_themes_drive_market_theme_detector(self):
        snapshot = get_market_snapshot("2026-05-08")
        context = {
            "marketSnapshot": snapshot,
            "sectorStats": {},
            **snapshot["data"],
        }
        coverage = data_coverage_panel(context)

        theme = detect_market_themes(context, [], coverage)

        self.assertEqual(theme["themes"][0]["name"], "商业航天")
        self.assertEqual(theme["themes"][0]["confidence"], "中")
        self.assertIn("商业航天", theme["displayText"])


if __name__ == "__main__":
    unittest.main()
