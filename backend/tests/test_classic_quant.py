import unittest

import pandas as pd

from app.services.classic_quant import (
    evaluate_classic_strategy,
    market_regime_model,
    portfolio_risk_budget,
    research_integrity_check,
)


def _frame(close_values: list[float], pct_values: list[float] | None = None) -> pd.DataFrame:
    size = len(close_values)
    pct = pct_values or [0.3 for _ in range(size)]
    dates = pd.date_range("2026-01-01", periods=size, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "open": close_values,
            "high": [value * 1.02 for value in close_values],
            "low": [value * 0.98 for value in close_values],
            "close": close_values,
            "volume": [12000000 + index * 1000 for index in range(size)],
            "amount": [180000000 + index * 1200000 for index in range(size)],
            "pct_change": pct,
            "ma20": pd.Series(close_values).rolling(20).mean(),
            "ma60": pd.Series(close_values).rolling(60).mean(),
            "high20": pd.Series([value * 1.02 for value in close_values]).rolling(20).max(),
            "high60": pd.Series([value * 1.02 for value in close_values]).rolling(60).max(),
            "high120": pd.Series([value * 1.02 for value in close_values]).rolling(120).max(),
            "amount_ma20": [150000000 for _ in range(size)],
            "volume_ma20": [10000000 for _ in range(size)],
            "ret20": pd.Series(close_values) / pd.Series(close_values).shift(20) - 1,
            "ret60": pd.Series(close_values) / pd.Series(close_values).shift(60) - 1,
            "ret120": pd.Series(close_values) / pd.Series(close_values).shift(120) - 1,
            "volatility_20": [0.18 for _ in range(size)],
            "volatility_60": [0.2 for _ in range(size)],
            "volatility_120": [0.22 for _ in range(size)],
            "max_drawdown_60": [0.12 for _ in range(size)],
            "max_drawdown_120": [0.16 for _ in range(size)],
            "trend_slope": [0.04 for _ in range(size)],
        }
    )


class ClassicQuantTest(unittest.TestCase):
    def test_market_regime_identifies_risk_on(self):
        frames = []
        for index in range(80):
            stock = {"code": f"000{index:03d}", "name": f"样本{index}", "industry": "测试", "market": "SZ"}
            close = [10 + cursor * 0.06 for cursor in range(80)]
            pct = [0.5 for _ in range(79)] + ([10.1] if index < 55 else [0.8])
            frames.append({"stock": stock, "frame": _frame(close, pct)})

        context = market_regime_model(frames, "2026-03-21")

        self.assertEqual(context["marketRegime"], "RiskOn")
        self.assertIn("趋势跟踪策略", context["enabledStrategies"])
        self.assertGreater(context["suggestedTotalPosition"], 0.6)

    def test_intraday_super_risk_on_override_upgrades_riskoff_model(self):
        frames = []
        for index in range(80):
            stock = {"code": f"600{index:03d}", "name": f"弱势样本{index}", "industry": "测试", "market": "SH"}
            close = [30 - cursor * 0.08 for cursor in range(80)]
            pct = [-0.4 for _ in range(79)] + [-0.8]
            frames.append({"stock": stock, "frame": _frame(close, pct)})

        context = market_regime_model(
            frames,
            "2026-03-21",
            market_snapshot={
                "shIndexPctChg": 1.17,
                "szIndexPctChg": 2.33,
                "cybIndexPctChg": 2.75,
                "kc50PctChg": 5.47,
                "totalAmount": 3250000000000,
                "totalAmountChange": 0.22,
                "upStockCount": 3900,
                "downStockCount": 1200,
                "upStockRatio": 0.75,
                "limitUpCount": 118,
                "limitDownCount": 6,
                "strongSectorCount": 6,
                "topSectorAvgPct": 5.2,
                "growthStyleStrength": 4.1,
            },
        )

        self.assertEqual(context["rawMarketRegime"], "RiskOff")
        self.assertEqual(context["marketRegime"], "RiskOn")
        self.assertTrue(context["superRiskOnSignal"])
        self.assertTrue(context["intradayRecoveryOverride"])
        self.assertTrue(any("放量普涨" in item for item in context["regimeReasons"]))

    def test_value_momentum_outputs_unified_candidate(self):
        stock = {
            "code": "002415",
            "name": "海康威视",
            "industry": "计算机",
            "market": "SZ",
            "list_date": "2020-01-01",
            "is_st": 0,
            "is_suspended": 0,
            "float_market_cap": 8000000000,
        }
        frame = _frame([20 + index * 0.12 for index in range(140)])
        context = {
            "marketRegime": "RiskOn",
            "indexReturn20d": 2.0,
            "upStockRatio": 0.62,
            "strategyPosture": {"ValueMomentumStrategy": "enabled"},
        }
        strategy = {"name": "价值动量策略", "parameters": {"strategy_class": "ValueMomentumStrategy"}}

        signal = evaluate_classic_strategy(strategy, stock, frame, context)

        self.assertIsNotNone(signal)
        assert signal is not None
        candidate = signal["metadata"]["strategyCandidate"]
        self.assertEqual(candidate["strategyName"], "价值动量策略")
        self.assertEqual(candidate["marketRegime"], "RiskOn")
        self.assertIn(candidate["suggestedAction"], {"观察", "谨慎观察", "暂不参与"})
        self.assertGreaterEqual(candidate["finalScore"], 0)
        self.assertIn("triggerReasons", candidate)
        self.assertIn("rawFactors", candidate)

    def test_market_hotspot_outputs_candidate_with_industry_fallback(self):
        stock = {
            "code": "300750",
            "name": "宁德时代",
            "industry": "电力设备",
            "market": "SZ",
            "list_date": "2020-01-01",
            "is_st": 0,
            "is_suspended": 0,
            "float_market_cap": 12000000000,
        }
        close_values = [20 + index * 0.05 for index in range(130)] + [28, 29.8, 31.7, 33.5, 36.3]
        pct_values = [0.3 for _ in range(130)] + [7.2, 6.4, 6.1, 5.7, 8.4]
        frame = _frame(close_values, pct_values)
        frame["ma5"] = frame["close"].rolling(5).mean()
        frame["ma10"] = frame["close"].rolling(10).mean()
        frame["ret3"] = frame["close"] / frame["close"].shift(3) - 1
        frame["ret5"] = frame["close"] / frame["close"].shift(5) - 1
        frame["ret10"] = frame["close"] / frame["close"].shift(10) - 1
        context = {
            "marketRegime": "RiskOn",
            "upStockRatio": 0.68,
            "limitUpCount": 70,
            "limitDownCount": 5,
            "strategyPosture": {"MarketHotspotStrategy": "enabled"},
            "sectorStats": {
                "电力设备": {
                    "sectorPctChg": 5.8,
                    "sectorRank": 2,
                    "sectorLimitUpCount": 4,
                    "sectorStrongStockCount": 8,
                    "sectorAmountChange": 0.42,
                    "sectorHotRank": 2,
                }
            },
        }
        strategy = {"name": "市场热点候选策略", "parameters": {"strategy_class": "MarketHotspotStrategy"}}

        signal = evaluate_classic_strategy(strategy, stock, frame, context)

        self.assertIsNotNone(signal)
        assert signal is not None
        candidate = signal["metadata"]["strategyCandidate"]
        self.assertEqual(candidate["strategyName"], "市场热点候选策略")
        self.assertIn("热点题材", candidate["candidateTypes"])
        self.assertIn("短线强势", candidate["candidateTypes"])
        self.assertGreaterEqual(candidate["hotspotScore"], 60)
        self.assertIn("sectorHotScore", candidate["subScores"])
        self.assertTrue(any("行业热度" in item or "题材数据暂缺" in item for item in candidate["triggerReasons"]))
        self.assertNotIn(candidate["suggestedAction"], {"买入", "强烈推荐"})

    def test_riskon_hotspot_uses_looser_drawdown_and_volatility_thresholds(self):
        stock = {
            "code": "688001",
            "name": "科技样本",
            "industry": "计算机",
            "market": "SH",
            "list_date": "2020-01-01",
            "is_st": 0,
            "is_suspended": 0,
            "float_market_cap": 12000000000,
        }
        close_values = [20 + index * 0.03 for index in range(130)] + [25, 26.2, 27.5, 28.4, 30.1]
        pct_values = [0.2 for _ in range(130)] + [5.8, 4.8, 5.0, 3.2, 6.0]
        frame = _frame(close_values, pct_values)
        frame["ma5"] = frame["close"].rolling(5).mean()
        frame["ma10"] = frame["close"].rolling(10).mean()
        frame["ret3"] = frame["close"] / frame["close"].shift(3) - 1
        frame["ret5"] = frame["close"] / frame["close"].shift(5) - 1
        frame["ret10"] = frame["close"] / frame["close"].shift(10) - 1
        frame["max_drawdown_60"] = 0.32
        frame["volatility_60"] = 0.42
        context = {
            "marketRegime": "RiskOn",
            "strategyPosture": {"MarketHotspotStrategy": "enabled"},
            "sectorStats": {
                "计算机": {
                    "sectorPctChg": 5.2,
                    "sectorRank": 1,
                    "sectorLimitUpCount": 5,
                    "sectorStrongStockCount": 10,
                    "sectorAmountChange": 0.55,
                    "sectorHotRank": 1,
                }
            },
        }
        strategy = {"name": "市场热点候选策略", "parameters": {"strategy_class": "MarketHotspotStrategy"}}

        signal = evaluate_classic_strategy(strategy, stock, frame, context)

        self.assertIsNotNone(signal)
        assert signal is not None
        candidate = signal["metadata"]["strategyCandidate"]
        self.assertNotEqual(signal["risk_level"], "high")
        self.assertIn(candidate["candidateMode"], {"main_observation", "review_pool"})
        self.assertGreaterEqual(candidate["finalScore"], 55)

    def test_low_beta_strategy_respects_panic_observation_only(self):
        stock = {
            "code": "600887",
            "name": "伊利股份",
            "industry": "食品饮料",
            "market": "SH",
            "list_date": "2020-01-01",
            "is_st": 0,
            "is_suspended": 0,
            "float_market_cap": 9000000000,
        }
        frame = _frame([30 + index * 0.01 for index in range(140)])
        context = {"marketRegime": "Panic", "strategyPosture": {"LowBetaDefensiveStrategy": "enabled"}}
        strategy = {"name": "低波防御策略", "parameters": {"strategy_class": "LowBetaDefensiveStrategy"}}

        signal = evaluate_classic_strategy(strategy, stock, frame, context)

        self.assertIsNotNone(signal)
        assert signal is not None
        candidate = signal["metadata"]["strategyCandidate"]
        self.assertEqual(candidate["suggestedAction"], "暂不参与")
        self.assertEqual(candidate["suggestedWeight"], 0)
        self.assertIn("Panic", candidate["riskReasons"][0])

    def test_portfolio_budget_sets_high_risk_weight_to_zero(self):
        candidates = [
            {"code": "000001", "riskLevel": "高", "rawFactors": {"volatility60d": 0.3}, "strategyName": "价值动量策略", "sectorName": "银行"},
            {"code": "600887", "riskLevel": "低", "rawFactors": {"volatility60d": 0.15}, "strategyName": "低波防御策略", "sectorName": "食品饮料"},
        ]

        budget = portfolio_risk_budget(candidates, "RiskOff")

        by_code = {item["code"]: item for item in budget["positions"]}
        self.assertEqual(by_code["000001"]["suggestedWeight"], 0)
        self.assertLessEqual(budget["totalSuggestedWeight"], 0.3)

    def test_research_integrity_checker_flags_missing_data_versions(self):
        result = research_integrity_check(
            {
                "lookaheadBiasChecked": True,
                "financialAnnouncementLag": True,
                "survivorshipBiasChecked": True,
                "stSuspensionDelistHandled": True,
                "transactionCost": True,
                "slippage": False,
                "parameterVersion": True,
                "dataVersion": None,
                "runTimestamp": True,
                "reproducibleTradeDate": True,
            }
        )

        self.assertLess(result["integrityScore"], 100)
        self.assertEqual(result["integrityLevel"], "需谨慎")
        self.assertTrue(any("滑点" in item for item in result["integrityWarnings"]))


if __name__ == "__main__":
    unittest.main()
