import unittest

from app.services.limit_up_strategy_service import (
    calculate_market_sentiment,
    score_limit_up_signal,
)


class LimitUpStrategyServiceTest(unittest.TestCase):
    def test_market_sentiment_classifies_strong_limit_up_day(self):
        sentiment = calculate_market_sentiment(
            {
                "limitUpCount": 147,
                "limitDownCount": 36,
                "brokenLimitCount": 0,
                "highestBoard": 7,
                "thirdPlusCount": 2,
            }
        )

        self.assertGreaterEqual(sentiment["marketSentimentScore"], 75)
        self.assertEqual(sentiment["marketState"], "强情绪")

    def test_market_sentiment_classifies_weak_fading_day(self):
        sentiment = calculate_market_sentiment(
            {
                "limitUpCount": 18,
                "limitDownCount": 85,
                "brokenLimitCount": 24,
                "highestBoard": 2,
                "thirdPlusCount": 0,
            }
        )

        self.assertLess(sentiment["marketSentimentScore"], 45)
        self.assertEqual(sentiment["marketState"], "退潮")

    def test_signal_hard_risk_forces_forbidden_action(self):
        signal = score_limit_up_signal(
            {
                "code": "002001",
                "name": "*ST测试",
                "boardHeight": 3,
                "amount": 500000000,
                "turnoverRate": 8,
                "isOneWordBoard": False,
                "isNewHigh": True,
            },
            {"marketSentimentScore": 82, "marketState": "强情绪"},
            {"industryHeatScore": 92, "industryHeatRank": 1, "industryLineType": "主线板块"},
        )

        self.assertEqual(signal["actionLabel"], "禁止参与")
        self.assertLessEqual(signal["totalScore"], 49)
        self.assertTrue(any("ST" in reason for reason in signal["riskReasons"]))

    def test_high_score_mainline_stock_gets_participation_plan(self):
        signal = score_limit_up_signal(
            {
                "code": "002281",
                "name": "光迅科技",
                "boardHeight": 2,
                "amount": 2600000000,
                "turnoverRate": 10,
                "isOneWordBoard": False,
                "isNewHigh": True,
            },
            {"marketSentimentScore": 82, "marketState": "强情绪"},
            {"industryHeatScore": 95, "industryHeatRank": 1, "industryLineType": "主线板块"},
        )

        self.assertEqual(signal["actionLabel"], "可参与")
        self.assertEqual(signal["actionLevel"], "A")
        self.assertGreaterEqual(signal["totalScore"], 80)
        self.assertIn("次日", signal["triggerCondition"])
        self.assertIn("不构成投资建议", signal["positionAdvice"])


if __name__ == "__main__":
    unittest.main()
