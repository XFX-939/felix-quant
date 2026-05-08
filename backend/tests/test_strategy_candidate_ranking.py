import unittest

import pandas as pd

from app.services.dragon_leader_strategy import evaluate_dragon_observation_candidate, prepare_dragon_context
from app.services.strategy_rules import evaluate_strategy_row


def strategy(name: str, parameters: dict | None = None) -> dict:
    return {"id": 1, "name": name, "parameters": parameters or {}}


class StrategyCandidateRankingTest(unittest.TestCase):
    def test_moving_average_high_risk_is_capped_and_not_formal_candidate(self):
        row = pd.Series(
            {
                "close": 36.2,
                "pct_change": 4.2,
                "volume": 4200000,
                "volume_ma20": 2500000,
                "amount": 420000000,
                "ma20": 34.2,
                "ma60": 32.5,
                "ma20_slope": 0.03,
                "ma60_slope": 0.01,
                "ret20": 0.16,
                "ret60": 0.18,
                "volatility_60": 0.38,
                "max_drawdown_60": 0.32,
                "trend_slope": 0.052,
            }
        )
        moving_average = strategy("均线趋势策略", {"min_score": 60})

        signal = evaluate_strategy_row(
            moving_average,
            row,
            market_volatility=0.25,
            relaxed=True,
            market_context={"marketRegime": "RiskOff", "indexReturn20d": 3.0},
        )

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertLessEqual(signal["score"], 59)
        self.assertEqual(signal["risk_level"], "medium")
        self.assertEqual(signal["metadata"]["candidateMode"], "risk_observation")
        self.assertEqual(signal["metadata"]["candidateLevel"], "观察候选")
        self.assertIn("未满足均线趋势硬条件", signal["risk_reason"])
        self.assertIn("riskPenalty", signal["metadata"])

    def test_moving_average_hard_conditions_can_enter_main_observation(self):
        row = pd.Series(
            {
                "close": 18.4,
                "pct_change": 1.2,
                "volume": 3500000,
                "volume_ma20": 2600000,
                "amount": 260000000,
                "ma20": 17.6,
                "ma60": 16.2,
                "ma20_slope": 0.025,
                "ma60_slope": 0.006,
                "ret20": 0.08,
                "ret60": 0.14,
                "volatility_60": 0.22,
                "max_drawdown_60": 0.14,
                "trend_slope": 0.086,
            }
        )
        moving_average = strategy("均线趋势策略", {"min_score": 60})

        signal = evaluate_strategy_row(
            moving_average,
            row,
            market_volatility=0.22,
            relaxed=True,
            market_context={"marketRegime": "RiskOn", "indexReturn20d": 2.5},
        )

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal["metadata"]["candidateMode"], "main_observation")
        self.assertEqual(signal["risk_level"], "low")
        self.assertGreaterEqual(signal["score"], 60)
        self.assertIn("marketRegime", signal["metadata"])

    def test_low_drawdown_relaxed_mode_returns_observation_candidate(self):
        row = pd.Series(
            {
                "close": 12.4,
                "pct_change": 0.8,
                "volume": 180,
                "volume_ma20": 150,
                "ma20": 12.1,
                "ma60": 12.6,
                "ret20": 0.03,
                "ret60": 0.06,
                "volatility_60": 0.22,
                "max_drawdown_60": 0.17,
                "trend_slope": -0.04,
            }
        )
        low_drawdown = strategy(
            "低回撤趋势策略",
            {"min_score": 60, "max_drawdown_threshold": 0.16, "volatility_threshold": 0.18},
        )

        self.assertIsNone(evaluate_strategy_row(low_drawdown, row, market_volatility=0.22))

        signal = evaluate_strategy_row(low_drawdown, row, market_volatility=0.22, relaxed=True)

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertIn(signal["metadata"]["candidateMode"], {"ranked_observation", "review_pool", "risk_observation"})
        self.assertIn(signal["metadata"]["suggestedAction"], {"观察", "暂不参与"})
        self.assertTrue("按相关性进入观察池" in signal["reason"] or "未满足低回撤趋势硬条件" in signal["reason"])

    def test_multi_factor_relaxed_mode_returns_best_relevance_rows(self):
        row = pd.Series(
            {
                "close": 36.2,
                "pct_change": 3.2,
                "volume": 300,
                "volume_ma20": 150,
                "ma20": 34.2,
                "ma60": 32.5,
                "ret20": 0.13,
                "ret60": 0.18,
                "volatility_60": 0.28,
                "max_drawdown_60": 0.2,
                "trend_slope": 0.052,
            }
        )
        multi_factor = strategy(
            "多因子评分策略",
            {
                "min_score": 60,
                "weights": {"momentum": 0.25, "volatility": 0.2, "volume": 0.15, "drawdown": 0.2, "trend": 0.2},
            },
        )

        signal = evaluate_strategy_row(multi_factor, row, market_volatility=0.25, relaxed=True)

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertGreaterEqual(signal["score"], 30)
        self.assertIn(signal["metadata"]["candidateMode"], {"ranked_observation", "review_pool", "risk_observation"})
        self.assertIn("多因子相关性", signal["reason"])

    def test_dragon_observation_candidate_marks_missing_hard_trigger(self):
        dates = pd.date_range("2026-04-01", periods=70, freq="D")
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": [10 + index * 0.04 for index in range(70)],
                "high": [10.2 + index * 0.04 for index in range(70)],
                "low": [9.9 + index * 0.04 for index in range(70)],
                "close": [10.05 + index * 0.04 for index in range(70)],
                "volume": [1000000 + index * 4000 for index in range(70)],
                "amount": [250000000 + index * 1000000 for index in range(70)],
                "pct_change": [0.6 for _ in range(70)],
                "ma5": [10 + index * 0.04 for index in range(70)],
                "ma20": [9.8 + index * 0.04 for index in range(70)],
                "ma60": [9.5 + index * 0.035 for index in range(70)],
                "high20": [10.2 + index * 0.04 for index in range(70)],
                "volume_ma5": [950000 + index * 3500 for index in range(70)],
                "amount_ma5": [230000000 + index * 900000 for index in range(70)],
                "ret5": [0.08 for _ in range(70)],
                "ret10": [0.12 for _ in range(70)],
                "ret20": [0.18 for _ in range(70)],
                "ret60": [0.22 for _ in range(70)],
            }
        )
        stock = {
            "code": "002415",
            "name": "海康威视",
            "industry": "计算机",
            "market": "SZ",
            "float_market_cap": 8000000000,
            "is_st": 0,
            "is_suspended": 0,
        }
        context = prepare_dragon_context([{"stock": stock, "frame": frame}], dates[-1].date().isoformat())
        context["marketSentiment"] = "Neutral"
        context["indexPctChg"] = -0.8
        context["indexReturn5d"] = 2.0
        context["indexReturn20d"] = 8.0
        context["sectorStats"]["计算机"]["sectorLimitUpCount"] = 2

        signal, diagnostics = evaluate_dragon_observation_candidate(
            strategy("短线龙头候选策略", {"strategy_class": "DragonLeaderStrategy"}),
            stock,
            frame,
            context,
        )

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertTrue(diagnostics.base_filter_passed)
        self.assertFalse(diagnostics.hit_limit_or_breakout)
        self.assertEqual(signal["metadata"]["candidateLevel"], "观察候选")
        self.assertEqual(signal["metadata"]["suggestedAction"], "观察")
        self.assertIn("未触发涨停或强势突破", signal["risk_reason"])


if __name__ == "__main__":
    unittest.main()
