import unittest

from app.services.decision_engine import (
    build_daily_decision,
    build_position_decision,
    data_coverage_panel,
    detect_market_themes,
    evaluate_missed_opportunity_risk,
    evaluate_strategy_health,
    split_candidate_layers,
)


class DecisionEngineTest(unittest.TestCase):
    def test_riskoff_without_main_watchlist_outputs_defensive_observe(self):
        signals = [
            {
                "strategy_name": "低波防御策略",
                "score": 53,
                "risk_level": "low",
                "suggestedAction": "观察",
                "candidateMode": "review_pool",
                "candidateTypes": ["低波防御"],
                "marketRegime": "RiskOff",
            },
            {
                "strategy_name": "均线趋势策略",
                "score": 59,
                "risk_level": "medium",
                "suggestedAction": "观察",
                "candidateMode": "risk_observation",
                "candidateTypes": ["中期趋势"],
                "marketRegime": "RiskOff",
            },
        ]
        layers = split_candidate_layers(signals, "RiskOff")
        health = evaluate_strategy_health(signals, [], "RiskOff")

        decision = build_daily_decision("2026-05-06", "RiskOff", layers, health)

        self.assertEqual(decision["decisionMode"], "DEFENSIVE_OBSERVE")
        self.assertEqual(decision["suggestedTotalPositionMax"], 0.0)
        self.assertIn("观察低波防御", decision["allowedActions"])
        self.assertTrue(any("主观察清单为空" in item for item in decision["keyReasons"]))

    def test_high_risk_ratio_downgrades_probe_to_watch(self):
        signals = [
            {
                "strategy_name": "市场热点候选策略",
                "stock_code": "300001",
                "score": 84,
                "risk_level": "low",
                "suggestedAction": "谨慎观察",
                "candidateMode": "main_observation",
                "candidateTypes": ["热点题材"],
                "marketRegime": "RiskOn",
            },
            {
                "strategy_name": "市场热点候选策略",
                "stock_code": "300002",
                "score": 82,
                "risk_level": "low",
                "suggestedAction": "观察",
                "candidateMode": "main_observation",
                "candidateTypes": ["短线强势"],
                "marketRegime": "RiskOn",
            },
            {
                "strategy_name": "短线龙头候选策略",
                "stock_code": "300003",
                "score": 78,
                "risk_level": "low",
                "suggestedAction": "观察",
                "candidateMode": "main_observation",
                "candidateTypes": ["龙头候选"],
                "marketRegime": "RiskOn",
            },
            {
                "strategy_name": "短线龙头候选策略",
                "stock_code": "300004",
                "score": 50,
                "risk_level": "high",
                "suggestedAction": "暂不参与",
                "candidateMode": "risk_observation",
                "candidateTypes": ["风险观察"],
                "marketRegime": "RiskOn",
            },
            {
                "strategy_name": "均线趋势策略",
                "stock_code": "300005",
                "score": 48,
                "risk_level": "high",
                "suggestedAction": "暂不参与",
                "candidateMode": "risk_observation",
                "candidateTypes": ["风险观察"],
                "marketRegime": "RiskOn",
            },
            {
                "strategy_name": "均线趋势策略",
                "stock_code": "300006",
                "score": 44,
                "risk_level": "high",
                "suggestedAction": "暂不参与",
                "candidateMode": "risk_observation",
                "candidateTypes": ["风险观察"],
                "marketRegime": "RiskOn",
            },
            {
                "strategy_name": "多因子评分策略",
                "stock_code": "300007",
                "score": 42,
                "risk_level": "high",
                "suggestedAction": "暂不参与",
                "candidateMode": "risk_observation",
                "candidateTypes": ["风险观察"],
                "marketRegime": "RiskOn",
            },
        ]
        layers = split_candidate_layers(signals, "RiskOn")
        health = evaluate_strategy_health(signals, [], "RiskOn")

        decision = build_daily_decision("2026-05-06", "RiskOn", layers, health)

        self.assertEqual(decision["decisionMode"], "DEFENSIVE_OBSERVE")
        self.assertTrue(any("高风险候选比例过高" in item for item in decision["keyReasons"]))

    def test_wait_mode_after_downgrade_has_zero_position(self):
        signals = [
            {
                "strategy_name": "均线趋势策略",
                "stock_code": f"60000{index}",
                "score": 38,
                "risk_level": "high",
                "suggestedAction": "暂不参与",
                "candidateMode": "risk_observation",
                "candidateTypes": ["风险观察"],
                "marketRegime": "RiskOff",
            }
            for index in range(4)
        ]
        layers = split_candidate_layers(signals, "RiskOff")
        health = evaluate_strategy_health(signals, [], "RiskOff")

        decision = build_daily_decision("2026-05-06", "RiskOff", layers, health)

        self.assertEqual(decision["decisionMode"], "WAIT")
        self.assertEqual(decision["suggestedTotalPositionMin"], 0.0)
        self.assertEqual(decision["suggestedTotalPositionMax"], 0.0)
        self.assertIn("扩大仓位", decision["forbiddenActions"])

    def test_position_decision_uses_same_final_range_as_daily_decision(self):
        signals = [
            {
                "strategy_name": "低波防御策略",
                "stock_code": "600001",
                "score": 62,
                "risk_level": "low",
                "suggestedAction": "观察",
                "candidateMode": "main_observation",
                "candidateTypes": ["低波防御"],
                "marketRegime": "Choppy",
            }
        ]
        layers = split_candidate_layers(signals, "Choppy")
        health = evaluate_strategy_health(signals, [], "Choppy")
        decision = build_daily_decision("2026-05-06", "Choppy", layers, health)
        position = build_position_decision("Choppy", layers, health, decision["decisionMode"])

        self.assertEqual(decision["suggestedTotalPositionMin"], position["finalPositionMin"])
        self.assertEqual(decision["suggestedTotalPositionMax"], position["finalPositionMax"])
        self.assertLessEqual(position["finalPositionMax"], 0.3)

    def test_recovery_override_outputs_watch_instead_of_wait(self):
        layers = split_candidate_layers([], "Recovery")
        health = [
            {"strategyName": "市场热点候选策略", "status": "降权", "averageScore": 0, "candidateCount": 0, "mainCount": 0, "highRiskCount": 0, "highRiskRatio": 0},
            {"strategyName": "趋势跟踪策略", "status": "降权", "averageScore": 0, "candidateCount": 0, "mainCount": 0, "highRiskCount": 0, "highRiskRatio": 0},
        ]

        decision = build_daily_decision(
            "2026-05-06",
            "Recovery",
            layers,
            health,
            market_context={"intradayRecoveryOverride": True, "strongRecoverySignal": True},
        )

        self.assertEqual(decision["decisionMode"], "WATCH")
        self.assertGreaterEqual(decision["suggestedTotalPositionMin"], 0.1)
        self.assertEqual(decision["suggestedTotalPositionMax"], 0.3)
        self.assertIn("观察主线强势股", decision["allowedActions"])
        self.assertNotIn("趋势突破", decision["forbiddenActions"])

    def test_riskon_override_outputs_probe_with_controlled_position(self):
        signals = [
            {
                "strategy_name": "市场热点候选策略",
                "stock_code": f"30000{index}",
                "score": 76 + index,
                "risk_level": "low",
                "suggestedAction": "观察",
                "candidateMode": "main_observation",
                "candidateTypes": ["热点题材"],
                "marketRegime": "RiskOn",
            }
            for index in range(3)
        ]
        layers = split_candidate_layers(signals, "RiskOn")
        health = evaluate_strategy_health(signals, [], "RiskOn")

        decision = build_daily_decision(
            "2026-05-06",
            "RiskOn",
            layers,
            health,
            market_context={"intradayRecoveryOverride": True, "superRiskOnSignal": True},
        )

        self.assertEqual(decision["decisionMode"], "PROBE")
        self.assertEqual(decision["suggestedTotalPositionMin"], 0.2)
        self.assertEqual(decision["suggestedTotalPositionMax"], 0.5)
        self.assertIn("观察主线龙头", decision["allowedActions"])

    def test_riskon_probe_requires_visible_actionable_candidates(self):
        layers = split_candidate_layers([], "RiskOn")
        health = [{"strategyName": "市场热点候选策略", "status": "降权", "candidateCount": 0, "mainCount": 0, "highRiskCount": 0, "averageScore": 0, "highRiskRatio": 0}]

        decision = build_daily_decision(
            "2026-05-06",
            "RiskOn",
            layers,
            health,
            market_context={"intradayRecoveryOverride": True, "superRiskOnSignal": True},
        )

        self.assertEqual(decision["decisionMode"], "WATCH")
        self.assertTrue(any("无明确可观察标的" in item for item in decision["keyReasons"]))

    def test_theme_mapper_allows_growth_candidate_into_hotspot_watchlist(self):
        signals = [
            {
                "strategy_name": "市场热点候选策略",
                "stock_code": "688001",
                "stock_name": "科技样本",
                "industry": "计算机",
                "score": 56,
                "hotspotScore": 56,
                "risk_level": "medium",
                "suggestedAction": "观察",
                "candidateMode": "review_pool",
                "candidateTypes": ["热点题材"],
                "rawFactors": {
                    "sectorName": "计算机",
                    "conceptNames": ["算力"],
                    "pctChg": 5.8,
                    "amountRatio20d": 1.9,
                    "volumeRatio": 1.2,
                    "return3d": 4.2,
                    "return5d": 8.0,
                    "closeAboveMa5": True,
                    "closeAboveMa10": True,
                },
            }
        ]
        theme = {
            "confidence": "中",
            "themes": [{"name": "科技成长", "relatedSectors": ["半导体", "存储芯片", "算力", "CPO", "PCB", "计算机"]}],
        }

        layers = split_candidate_layers(signals, "RiskOn", market_theme=theme)

        self.assertEqual(len(layers["hotspotWatchlist"]), 1)
        self.assertEqual(layers["hotspotWatchlist"][0]["stock_code"], "688001")

    def test_riskon_theme_filters_non_mainline_hotspot_candidates(self):
        signals = [
            {
                "strategy_name": "市场热点候选策略",
                "stock_code": "600887",
                "stock_name": "伊利股份",
                "industry": "食品饮料",
                "score": 68,
                "hotspotScore": 68,
                "risk_level": "medium",
                "suggestedAction": "观察",
                "candidateMode": "main_observation",
                "candidateTypes": ["热点题材"],
                "rawFactors": {
                    "industryName": "食品饮料",
                    "conceptNames": ["食品饮料"],
                    "pctChg": 6.0,
                    "return5d": 8.0,
                    "amountRatio20d": 2.0,
                    "closeAboveMa5": True,
                },
            }
        ]
        theme = {
            "confidence": "中",
            "themes": [{"name": "科技成长", "relatedSectors": ["半导体", "算力", "CPO", "PCB"]}],
        }

        layers = split_candidate_layers(signals, "RiskOn", market_theme=theme)

        self.assertEqual(layers["hotspotWatchlist"], [])

    def test_missed_opportunity_risk_flags_empty_main_in_riskon(self):
        layers = {"mainWatchlist": [], "hotspotWatchlist": [], "defensiveWatchlist": [], "riskPool": [], "reviewPool": []}
        theme = {"confidence": "中", "themes": [{"name": "科技成长"}]}
        funnel = {"strategyInitialCandidates": 80, "finalActionableCandidates": 0}

        risk = evaluate_missed_opportunity_risk("RiskOn", layers, theme, funnel)

        self.assertEqual(risk["level"], "高")
        self.assertTrue(any("RiskOn 状态下主观察清单为空" in item for item in risk["reasons"]))
        self.assertTrue(any("主线到个股映射失败" in item for item in risk["reasons"]))

    def test_missing_hotspot_data_marks_hotspot_and_dragon_as_not_decision_ready(self):
        strategies = [
            {"name": "市场热点候选策略", "enabled": True},
            {"name": "短线龙头候选策略", "enabled": True},
        ]
        health = evaluate_strategy_health([], strategies, "RiskOff", critical_hotspot_data_missing=True)

        hotspot = next(item for item in health if item["strategyName"] == "市场热点候选策略")
        dragon = next(item for item in health if item["strategyName"] == "短线龙头候选策略")
        self.assertEqual(hotspot["status"], "仅复盘")
        self.assertIn("数据不足", hotspot["reason"])
        self.assertEqual(dragon["status"], "暂停")
        self.assertIn("不可用", dragon["reason"])

    def test_missing_hotspot_data_is_degraded_observation_in_riskon(self):
        strategies = [
            {"name": "市场热点候选策略", "enabled": True},
            {"name": "短线龙头候选策略", "enabled": True},
            {"name": "趋势跟踪策略", "enabled": True},
            {"name": "低波防御策略", "enabled": True},
        ]
        health = evaluate_strategy_health([], strategies, "RiskOn", critical_hotspot_data_missing=True)

        hotspot = next(item for item in health if item["strategyName"] == "市场热点候选策略")
        dragon = next(item for item in health if item["strategyName"] == "短线龙头候选策略")
        defensive = next(item for item in health if item["strategyName"] == "低波防御策略")
        self.assertEqual(hotspot["status"], "降权")
        self.assertIn("降级估算", hotspot["reason"])
        self.assertEqual(dragon["status"], "降权")
        self.assertIn("降级观察", dragon["reason"])
        self.assertEqual(defensive["status"], "降权")

    def test_low_confidence_market_theme_is_industry_clue_not_official_theme(self):
        context = {
            "sectorStats": {
                "银行": {
                    "sectorPctChg": 3.2,
                    "sectorRank": 1,
                    "sectorLimitUpCount": 0,
                    "sectorStrongStockCount": 1,
                    "sectorAmountChange": 0.2,
                    "continuationDays": 1,
                }
            }
        }
        coverage = data_coverage_panel(context)
        theme = detect_market_themes(context, [], coverage)

        self.assertEqual(theme["confidence"], "低")
        self.assertIn("行业估算线索", theme["displayText"])
        self.assertFalse(theme["isComplete"])

    def test_style_theme_estimate_detects_growth_mainline_when_concept_data_missing(self):
        context = {
            "marketRegime": "RiskOn",
            "cybIndexPctChg": 2.75,
            "kc50PctChg": 5.47,
            "totalAmount": 3250000000000,
            "totalAmountChange": 0.22,
            "upStockRatio": 0.75,
            "limitUpCount": 118,
            "sectorStats": {
                "电子": {
                    "sectorPctChg": 5.2,
                    "sectorRank": 1,
                    "sectorLimitUpCount": 8,
                    "sectorStrongStockCount": 16,
                    "sectorAmountChange": 0.55,
                    "continuationDays": 1,
                }
            },
        }
        coverage = data_coverage_panel(context)
        theme = detect_market_themes(context, [], coverage)

        self.assertEqual(theme["confidence"], "中")
        self.assertIn("科技成长", theme["displayText"])
        self.assertEqual(theme["themes"][0]["level"], "风格估算")
        self.assertTrue(any("科创50" in item for item in theme["themes"][0]["evidence"]))


if __name__ == "__main__":
    unittest.main()
