from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services.analytics import enrich_prices, normalize, safe_float

RATING_VERSION = "stock-inspector-v1"
RATING_DISCLAIMER = (
    "本系统生成的评级仅用于个人量化研究和投资复盘，不构成任何投资建议或交易指令。"
    "评级基于历史数据、公开数据和模型规则生成，可能存在数据缺失、模型误差、前视偏差、"
    "滞后性和市场突发风险。投资有风险，决策需谨慎。"
)
RATING_ORDER = ["卖出", "减持", "持有", "增持", "买入"]


def get_stock_inspection_report(code: str, trade_date: str | None = None, force: bool = False) -> dict:
    normalized_code = code.strip()
    with get_connection() as conn:
        stock = conn.execute("SELECT * FROM stocks WHERE code = ?", (normalized_code,)).fetchone()
        if not stock:
            raise ValueError("stock not found")
        latest_date = trade_date or conn.execute("SELECT MAX(date) AS date FROM daily_prices WHERE stock_code = ?", (normalized_code,)).fetchone()["date"]
        if not latest_date:
            raise ValueError("stock has no price data")
        cached = None if force else conn.execute(
            "SELECT * FROM stock_diagnosis_reports WHERE code = ? AND trade_date = ?",
            (normalized_code, latest_date),
        ).fetchone()
        if cached:
            return _report_from_row(cached, dict_from_row(stock) or {})

    report = _build_report(dict_from_row(stock) or {}, latest_date)
    _persist_report(report)
    return report


def determine_research_rating(
    *,
    overall_score: float,
    risk_level: str,
    data_confidence: str,
    trend_status: str,
    market_regime: str,
    hard_risk_triggered: bool,
    is_st: bool,
    is_suspended: bool,
    listed_days: int | None,
    technical_score: float | None,
    fundamental_score: float | None,
    volatility_60: float | None,
    mainline_match: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    rating = _base_rating(overall_score, risk_level, data_confidence)

    if is_st or is_suspended or (listed_days is not None and listed_days < 60):
        reasons.append("ST、停牌、上市不足 60 日或退市风险等基础条件不满足，无法形成有效研究评级。")
        return {"researchRating": "无法评级", "ratingReasons": reasons}

    if hard_risk_triggered:
        reasons.append("触发硬风险条件，评级直接降至卖出或无法评级。")
        return {"researchRating": "卖出", "ratingReasons": reasons}

    if data_confidence == "低" and risk_level != "低":
        reasons.append("数据可信度低且风险等级不低，模型无法给出有效研究评级。")
        return {"researchRating": "无法评级", "ratingReasons": reasons}
    if data_confidence == "低":
        rating = _cap_rating(rating, "持有")
        reasons.append("数据可信度低，评级最高限制为持有。")

    if risk_level == "高" and trend_status == "下行":
        reasons.append("高风险且趋势下行，优先提示趋势破位和风险暴露。")
        return {"researchRating": "卖出", "ratingReasons": reasons}
    if risk_level == "高":
        rating = _cap_rating(rating, "减持")
        reasons.append("高风险股票即使信号分较高，评级最高限制为减持。")

    if market_regime == "Panic":
        rating = _cap_rating(rating, "持有")
        reasons.append("市场状态为 Panic，不允许输出买入，最高限制为持有。")
        if risk_level in {"中", "高"}:
            rating = _downgrade_rating(rating)
            reasons.append("Panic 中风险不低，评级额外下调一级。")
    elif market_regime == "RiskOff":
        if not (
            overall_score >= 90
            and risk_level == "低"
            and (technical_score or 0) >= 85
            and (fundamental_score or 0) >= 85
        ):
            rating = _cap_rating(rating, "增持")
            reasons.append("市场状态为 RiskOff，除非基本面和技术面同时极强，否则最高限制为增持。")
        if (volatility_60 or 0) > 0.35:
            rating = _downgrade_rating(rating)
            reasons.append("RiskOff 下高波动股票评级自动下调。")
    elif market_regime == "Choppy":
        if rating == "买入" and not (overall_score >= 88 and risk_level == "低"):
            rating = "增持"
            reasons.append("震荡市买入门槛提高，未达到 88 分且低风险时降为增持。")
    elif market_regime == "Recovery":
        reasons.append("市场处于 Recovery，允许积极评级，但修复行情需观察持续性。")
    elif market_regime == "RiskOn":
        reasons.append("市场处于 RiskOn，正常使用研究评级映射。")
        if mainline_match and data_confidence != "低" and rating in {"持有", "增持"} and overall_score >= 73 and risk_level != "高":
            upgraded = _upgrade_rating(rating)
            if upgraded != rating:
                rating = upgraded
                reasons.append("个股与当前主线匹配，评级在规则范围内适度上调。")

    return {"researchRating": rating, "ratingReasons": reasons}


def estimate_target_price_range(prices: list[dict], latest: dict | None) -> dict[str, Any]:
    if len(prices) < 60 or not latest:
        return {
            "low": None,
            "mid": None,
            "high": None,
            "method": "目标价区间数据不足，暂不输出。",
            "confidence": "低",
            "supportLevels": [],
            "resistanceLevels": [],
        }

    enriched = enrich_prices(prices)
    if enriched.empty:
        return {
            "low": None,
            "mid": None,
            "high": None,
            "method": "目标价区间数据不足，暂不输出。",
            "confidence": "低",
            "supportLevels": [],
            "resistanceLevels": [],
        }
    row = enriched.iloc[-1]
    close = safe_float(row.get("close"))
    support_values = [
        safe_float(row.get("ma20")),
        safe_float(row.get("ma60")),
        safe_float(row.get("low20")),
        safe_float(enriched.tail(60)["low"].min()),
    ]
    resistance_values = [
        safe_float(row.get("high20")),
        safe_float(row.get("high60")),
        safe_float(row.get("high120")),
    ]
    supports = sorted({round(value, 2) for value in support_values if value > 0})
    resistances = sorted({round(value, 2) for value in resistance_values if value > 0})
    if not supports or not resistances or close <= 0:
        return {
            "low": None,
            "mid": None,
            "high": None,
            "method": "目标价区间数据不足，暂不输出。",
            "confidence": "低",
            "supportLevels": supports,
            "resistanceLevels": resistances,
        }
    low = max([value for value in supports if value <= close] or [min(supports)])
    high = min([value for value in resistances if value >= close] or [max(resistances)])
    mid = round((low + high) / 2, 2)
    return {
        "low": round(low, 2),
        "mid": mid,
        "high": round(high, 2),
        "method": "技术区间法：参考 MA20、MA60、近 20/60 日低点及近 20/60/120 日高点。",
        "confidence": "中",
        "supportLevels": supports,
        "resistanceLevels": resistances,
    }


def _build_report(stock: dict, trade_date: str) -> dict:
    code = str(stock["code"])
    prices = _prices_for_report(code, trade_date)
    enriched = enrich_prices(prices)
    latest_row = enriched.iloc[-1].to_dict() if not enriched.empty else {}
    latest_price = prices[-1] if prices else {}
    latest_signal = _latest_signal(code, trade_date)
    market_regime = _market_regime_from_signal(latest_signal)
    listed_days = _listed_days(stock.get("list_date"), trade_date)
    is_st = bool(stock.get("is_st"))
    is_suspended = bool(stock.get("is_suspended"))
    trend_status = _trend_status(latest_row)
    technical_score = _technical_score(latest_row)
    sentiment_score = _sentiment_score(market_regime, latest_signal, stock)
    capital_flow_score = _capital_flow_score(latest_row)
    risk_control_score = _risk_control_score(latest_row, is_st=is_st, is_suspended=is_suspended, listed_days=listed_days)
    fundamental_score = _fundamental_score(stock, latest_signal)
    scores = {
        "technicalScore": technical_score,
        "fundamentalScore": fundamental_score,
        "sentimentScore": sentiment_score,
        "capitalFlowScore": capital_flow_score,
        "riskControlScore": risk_control_score,
    }
    overall_score = _weighted_overall_score(scores)
    risk_level = _risk_level(latest_row, is_st=is_st, is_suspended=is_suspended, listed_days=listed_days, price_count=len(prices))
    data_confidence, data_notes = _data_confidence(scores, prices, stock, latest_signal)
    hard_risk_triggered = _hard_risk_triggered(latest_row, is_st=is_st, is_suspended=is_suspended, listed_days=listed_days, price_count=len(prices))
    mainline_match = _mainline_match(stock, latest_signal)
    rating = determine_research_rating(
        overall_score=overall_score,
        risk_level=risk_level,
        data_confidence=data_confidence,
        trend_status=trend_status,
        market_regime=market_regime,
        hard_risk_triggered=hard_risk_triggered,
        is_st=is_st,
        is_suspended=is_suspended,
        listed_days=listed_days,
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        volatility_60=safe_float(latest_row.get("volatility_60"), 0),
        mainline_match=mainline_match,
    )
    research_rating = rating["researchRating"]
    target_range = estimate_target_price_range(prices, latest_price)
    key_bullish = _bullish_reasons(research_rating, scores, market_regime, latest_signal, trend_status, mainline_match)
    key_bearish = _bearish_reasons(research_rating, risk_level, data_confidence, latest_row, data_notes, market_regime)
    upgrade_triggers, downgrade_triggers = _rating_change_triggers(trend_status, market_regime)
    horizon = _rating_horizon(scores, latest_signal)
    rating_summary = _rating_summary(research_rating, overall_score, risk_level, data_confidence, market_regime, rating["ratingReasons"])
    return {
        "code": code,
        "name": stock.get("name") or code,
        "tradeDate": trade_date,
        "industry": stock.get("industry") or "未分类",
        "conceptNames": _concept_names(latest_signal),
        "marketRegime": market_regime,
        "researchRating": research_rating,
        "overallScore": overall_score,
        "riskLevel": risk_level,
        "dataConfidence": data_confidence,
        "ratingSummary": rating_summary,
        "ratingHorizon": horizon,
        "targetPriceRange": target_range,
        "currentPrice": _round(latest_price.get("close")),
        "pctChange": _round(latest_price.get("pct_change")),
        "supportLevels": target_range.get("supportLevels", []),
        "resistanceLevels": target_range.get("resistanceLevels", []),
        "keyBullishReasons": key_bullish,
        "keyBearishReasons": key_bearish,
        "ratingChangeTriggers": {
            "upgradeTriggers": upgrade_triggers,
            "downgradeTriggers": downgrade_triggers,
        },
        "scores": scores,
        "analysis": _analysis_sections(scores, latest_row, latest_signal, risk_level, data_notes),
        "ratingReasons": rating["ratingReasons"],
        "invalidConditions": _invalid_conditions(research_rating, trend_status, market_regime),
        "ratingDisclaimer": RATING_DISCLAIMER,
        "ratingVersion": RATING_VERSION,
        "updatedAt": now_iso(),
        "rawFactors": {
            "trendStatus": trend_status,
            "listedDays": listed_days,
            "isST": is_st,
            "isSuspended": is_suspended,
            "hardRiskTriggered": hard_risk_triggered,
            "mainlineMatch": mainline_match,
            "ma20": _round(latest_row.get("ma20")),
            "ma60": _round(latest_row.get("ma60")),
            "return20d": _round(latest_row.get("ret20")),
            "return60d": _round(latest_row.get("ret60")),
            "volatility60d": _round(latest_row.get("volatility_60")),
            "maxDrawdown60d": _round(latest_row.get("max_drawdown_60")),
            "amountRatio20d": _amount_ratio(latest_row),
            "latestSignal": latest_signal.get("strategy_name") if latest_signal else None,
        },
    }


def _persist_report(report: dict) -> None:
    timestamp = now_iso()
    target = report["targetPriceRange"]
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stock_diagnosis_reports (
                code, trade_date, research_rating, rating_horizon, rating_summary,
                target_price_low, target_price_mid, target_price_high, target_price_method, target_price_confidence,
                key_bullish_reasons_json, key_bearish_reasons_json, upgrade_triggers_json, downgrade_triggers_json,
                rating_disclaimer, rating_version, overall_score, technical_score, fundamental_score, sentiment_score,
                capital_flow_score, risk_control_score, risk_level, data_confidence, summary, raw_factors_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code, trade_date) DO UPDATE SET
                research_rating = excluded.research_rating,
                rating_horizon = excluded.rating_horizon,
                rating_summary = excluded.rating_summary,
                target_price_low = excluded.target_price_low,
                target_price_mid = excluded.target_price_mid,
                target_price_high = excluded.target_price_high,
                target_price_method = excluded.target_price_method,
                target_price_confidence = excluded.target_price_confidence,
                key_bullish_reasons_json = excluded.key_bullish_reasons_json,
                key_bearish_reasons_json = excluded.key_bearish_reasons_json,
                upgrade_triggers_json = excluded.upgrade_triggers_json,
                downgrade_triggers_json = excluded.downgrade_triggers_json,
                rating_disclaimer = excluded.rating_disclaimer,
                rating_version = excluded.rating_version,
                overall_score = excluded.overall_score,
                technical_score = excluded.technical_score,
                fundamental_score = excluded.fundamental_score,
                sentiment_score = excluded.sentiment_score,
                capital_flow_score = excluded.capital_flow_score,
                risk_control_score = excluded.risk_control_score,
                risk_level = excluded.risk_level,
                data_confidence = excluded.data_confidence,
                summary = excluded.summary,
                raw_factors_json = excluded.raw_factors_json,
                updated_at = excluded.updated_at
            """,
            (
                report["code"],
                report["tradeDate"],
                report["researchRating"],
                report["ratingHorizon"],
                report["ratingSummary"],
                target.get("low"),
                target.get("mid"),
                target.get("high"),
                target.get("method") or "",
                target.get("confidence") or "低",
                json.dumps(report["keyBullishReasons"], ensure_ascii=False),
                json.dumps(report["keyBearishReasons"], ensure_ascii=False),
                json.dumps(report["ratingChangeTriggers"]["upgradeTriggers"], ensure_ascii=False),
                json.dumps(report["ratingChangeTriggers"]["downgradeTriggers"], ensure_ascii=False),
                report["ratingDisclaimer"],
                report["ratingVersion"],
                report["overallScore"],
                report["scores"].get("technicalScore"),
                report["scores"].get("fundamentalScore"),
                report["scores"].get("sentimentScore"),
                report["scores"].get("capitalFlowScore"),
                report["scores"].get("riskControlScore"),
                report["riskLevel"],
                report["dataConfidence"],
                report["ratingSummary"],
                json.dumps(
                    {
                        "report": report,
                        "rawFactors": report["rawFactors"],
                        "analysis": report["analysis"],
                    },
                    ensure_ascii=False,
                ),
                timestamp,
                timestamp,
            ),
        )


def _report_from_row(row: Any, stock: dict) -> dict:
    data = dict_from_row(row) or {}
    raw = _json_loads(data.get("raw_factors_json"), {})
    if isinstance(raw, dict) and raw.get("report"):
        return raw["report"]
    return {
        "code": data["code"],
        "name": stock.get("name") or data["code"],
        "tradeDate": data["trade_date"],
        "industry": stock.get("industry") or "未分类",
        "marketRegime": "Choppy",
        "researchRating": data["research_rating"],
        "overallScore": data["overall_score"],
        "riskLevel": data["risk_level"],
        "dataConfidence": data["data_confidence"],
        "ratingSummary": data["rating_summary"],
        "ratingHorizon": data["rating_horizon"],
        "targetPriceRange": {
            "low": data.get("target_price_low"),
            "mid": data.get("target_price_mid"),
            "high": data.get("target_price_high"),
            "method": data.get("target_price_method"),
            "confidence": data.get("target_price_confidence"),
        },
        "keyBullishReasons": _json_loads(data.get("key_bullish_reasons_json"), []),
        "keyBearishReasons": _json_loads(data.get("key_bearish_reasons_json"), []),
        "ratingChangeTriggers": {
            "upgradeTriggers": _json_loads(data.get("upgrade_triggers_json"), []),
            "downgradeTriggers": _json_loads(data.get("downgrade_triggers_json"), []),
        },
        "scores": {
            "technicalScore": data.get("technical_score"),
            "fundamentalScore": data.get("fundamental_score"),
            "sentimentScore": data.get("sentiment_score"),
            "capitalFlowScore": data.get("capital_flow_score"),
            "riskControlScore": data.get("risk_control_score"),
        },
        "analysis": raw.get("analysis", {}) if isinstance(raw, dict) else {},
        "ratingDisclaimer": data["rating_disclaimer"],
        "ratingVersion": data["rating_version"],
        "updatedAt": data["updated_at"],
        "rawFactors": raw.get("rawFactors", {}) if isinstance(raw, dict) else {},
    }


def _base_rating(overall_score: float, risk_level: str, data_confidence: str) -> str:
    if data_confidence == "低":
        return "持有" if overall_score >= 60 else "减持" if overall_score >= 45 else "卖出"
    if overall_score >= 85 and risk_level == "低" and data_confidence == "高":
        return "买入"
    if overall_score >= 75 and risk_level in {"低", "中"}:
        return "增持"
    if overall_score >= 60:
        return "持有"
    if overall_score >= 45:
        return "减持"
    return "卖出"


def _cap_rating(rating: str, cap: str) -> str:
    if rating == "无法评级":
        return rating
    return rating if RATING_ORDER.index(rating) <= RATING_ORDER.index(cap) else cap


def _downgrade_rating(rating: str) -> str:
    if rating not in RATING_ORDER:
        return rating
    index = max(0, RATING_ORDER.index(rating) - 1)
    return RATING_ORDER[index]


def _upgrade_rating(rating: str) -> str:
    if rating not in RATING_ORDER:
        return rating
    index = min(len(RATING_ORDER) - 1, RATING_ORDER.index(rating) + 1)
    return RATING_ORDER[index]


def _weighted_overall_score(scores: dict[str, float | None]) -> float:
    weights = {
        "technicalScore": 0.25,
        "fundamentalScore": 0.25,
        "sentimentScore": 0.20,
        "capitalFlowScore": 0.15,
        "riskControlScore": 0.15,
    }
    weighted = 0.0
    total_weight = 0.0
    for key, weight in weights.items():
        value = scores.get(key)
        if value is None or math.isnan(float(value)):
            continue
        weighted += float(value) * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return round(weighted / total_weight, 2)


def _technical_score(row: dict) -> float | None:
    if not row:
        return None
    close = safe_float(row.get("close"))
    ma20 = safe_float(row.get("ma20"))
    ma60 = safe_float(row.get("ma60"))
    if close <= 0 or ma20 <= 0:
        return None
    trend = 70 if close > ma20 else 42
    if ma20 > ma60 > 0:
        trend += 12
    trend += normalize(safe_float(row.get("ret60")), -0.2, 0.35) * 0.28 - 14
    trend += normalize(safe_float(row.get("max_drawdown_60")), 0.04, 0.35, inverse=True) * 0.18 - 9
    trend += normalize(safe_float(row.get("volatility_60")), 0.08, 0.45, inverse=True) * 0.12 - 6
    return round(max(0, min(100, trend)), 2)


def _fundamental_score(stock: dict, signal: dict | None) -> float | None:
    if not signal:
        return None
    score = safe_float(signal.get("score"), 60)
    industry_bonus = 4 if stock.get("industry") in {"银行", "食品饮料", "医药生物", "电力设备", "半导体", "通信设备"} else 0
    return round(max(45, min(88, score - 4 + industry_bonus)), 2)


def _sentiment_score(market_regime: str, signal: dict | None, stock: dict) -> float:
    base = {
        "RiskOn": 78,
        "Recovery": 70,
        "Choppy": 58,
        "RiskOff": 42,
        "Panic": 28,
    }.get(market_regime, 55)
    if signal:
        metadata = _signal_metadata(signal)
        if metadata.get("hotspotScore"):
            base += min(14, safe_float(metadata.get("hotspotScore")) / 10)
        if _mainline_match(stock, signal):
            base += 8
    return round(max(0, min(100, base)), 2)


def _capital_flow_score(row: dict) -> float | None:
    if not row:
        return None
    amount_ratio = _amount_ratio(row)
    if amount_ratio is None:
        return None
    amount_score = normalize(amount_ratio, 0.6, 2.5)
    pct_score = normalize(safe_float(row.get("ret5")), -0.08, 0.18)
    return round(amount_score * 0.65 + pct_score * 0.35, 2)


def _risk_control_score(row: dict, *, is_st: bool, is_suspended: bool, listed_days: int | None) -> float:
    if is_st or is_suspended or (listed_days is not None and listed_days < 60):
        return 5.0
    drawdown = safe_float(row.get("max_drawdown_60"), 0.35)
    volatility = safe_float(row.get("volatility_60"), 0.45)
    drawdown_score = normalize(drawdown, 0.05, 0.4, inverse=True)
    volatility_score = normalize(volatility, 0.1, 0.5, inverse=True)
    return round(max(0, min(100, drawdown_score * 0.58 + volatility_score * 0.42)), 2)


def _risk_level(row: dict, *, is_st: bool, is_suspended: bool, listed_days: int | None, price_count: int) -> str:
    if is_st or is_suspended or price_count < 30 or (listed_days is not None and listed_days < 60):
        return "高"
    drawdown = safe_float(row.get("max_drawdown_60"))
    volatility = safe_float(row.get("volatility_60"))
    close = safe_float(row.get("close"))
    ma60 = safe_float(row.get("ma60"))
    ma60_slope = safe_float(row.get("ma60_slope"))
    if drawdown > 0.35 or volatility > 0.45 or (close < ma60 and ma60_slope < 0):
        return "高"
    if drawdown > 0.25 or volatility > 0.35:
        return "中"
    return "低"


def _hard_risk_triggered(row: dict, *, is_st: bool, is_suspended: bool, listed_days: int | None, price_count: int) -> bool:
    if is_st or is_suspended or price_count < 30 or (listed_days is not None and listed_days < 60):
        return True
    close = safe_float(row.get("close"))
    ma60 = safe_float(row.get("ma60"))
    ma60_slope = safe_float(row.get("ma60_slope"))
    return safe_float(row.get("max_drawdown_60")) > 0.35 or safe_float(row.get("volatility_60")) > 0.45 or (close < ma60 and ma60_slope < 0)


def _data_confidence(scores: dict[str, float | None], prices: list[dict], stock: dict, signal: dict | None) -> tuple[str, list[str]]:
    notes: list[str] = []
    available_count = sum(1 for value in scores.values() if value is not None)
    if len(prices) < 60:
        notes.append("日线数据不足 60 条")
    if scores.get("fundamentalScore") is None:
        notes.append("财务估值数据缺失，基本面维度未直接计入")
    if stock.get("list_date") is None:
        notes.append("上市日期缺失，上市天数校验降级")
    if not signal:
        notes.append("近期策略信号缺失，情绪和基本面代理信息不足")
    if len(prices) >= 120 and available_count >= 5 and not notes:
        return "高", notes
    if len(prices) >= 80 and available_count >= 4:
        return "中", notes
    return "低", notes


def _trend_status(row: dict) -> str:
    close = safe_float(row.get("close"))
    ma20 = safe_float(row.get("ma20"))
    ma60 = safe_float(row.get("ma60"))
    ma60_slope = safe_float(row.get("ma60_slope"))
    ret20 = safe_float(row.get("ret20"))
    if close > ma20 > ma60 and ret20 > 0:
        return "上行"
    if close < ma60 and ma60_slope < 0:
        return "下行"
    return "震荡"


def _market_regime_from_signal(signal: dict | None) -> str:
    metadata = _signal_metadata(signal)
    regime = metadata.get("marketRegime")
    if regime in {"RiskOn", "Recovery", "Choppy", "RiskOff", "Panic"}:
        return str(regime)
    return "Choppy"


def _latest_signal(code: str, trade_date: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT sig.*, st.name AS strategy_name
            FROM signals sig
            JOIN strategies st ON st.id = sig.strategy_id
            WHERE sig.stock_code = ? AND sig.date <= ?
            ORDER BY sig.date DESC, sig.score DESC
            LIMIT 1
            """,
            (code, trade_date),
        ).fetchone()
    return dict_from_row(row)


def _prices_for_report(code: str, trade_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT stock_code, date, open, high, low, close, volume, amount, pct_change
            FROM daily_prices
            WHERE stock_code = ? AND date <= ?
            ORDER BY date DESC
            LIMIT 180
            """,
            (code, trade_date),
        ).fetchall()
    return list(reversed(dicts_from_rows(rows)))


def _listed_days(list_date: str | None, trade_date: str) -> int | None:
    if not list_date:
        return None
    try:
        return (datetime.fromisoformat(trade_date).date() - datetime.fromisoformat(list_date).date()).days
    except ValueError:
        return None


def _signal_metadata(signal: dict | None) -> dict:
    if not signal:
        return {}
    raw = signal.get("metadata")
    if isinstance(raw, dict):
        return raw
    return _json_loads(raw, {})


def _mainline_match(stock: dict, signal: dict | None) -> bool:
    industry = str(stock.get("industry") or "")
    metadata = _signal_metadata(signal)
    candidate_types = metadata.get("candidateTypes") or []
    theme_words = ["半导体", "芯片", "算力", "CPO", "PCB", "通信", "电子", "计算机", "有色"]
    return any(word in industry for word in theme_words) or any(item in {"热点题材", "短线强势", "龙头候选"} for item in candidate_types)


def _concept_names(signal: dict | None) -> list[str]:
    metadata = _signal_metadata(signal)
    candidate = metadata.get("strategyCandidate") if isinstance(metadata.get("strategyCandidate"), dict) else {}
    concepts = candidate.get("conceptNames") or metadata.get("conceptNames") or []
    return [str(item) for item in concepts if item]


def _bullish_reasons(
    rating: str,
    scores: dict[str, float | None],
    market_regime: str,
    signal: dict | None,
    trend_status: str,
    mainline_match: bool,
) -> list[str]:
    reasons = []
    if rating in {"买入", "增持"}:
        reasons.append(f"综合评级为{rating}，综合评分和风险约束在当前规则下偏积极。")
    if (scores.get("technicalScore") or 0) >= 70:
        reasons.append(f"技术面评分 {scores['technicalScore']:.1f}，均线和相对强度表现较好。")
    if (scores.get("capitalFlowScore") or 0) >= 65:
        reasons.append(f"资金面评分 {scores['capitalFlowScore']:.1f}，成交活跃度相对较高。")
    if market_regime in {"RiskOn", "Recovery"}:
        reasons.append(f"市场状态为 {market_regime}，风险偏好较 RiskOff/Panic 阶段改善。")
    if mainline_match:
        reasons.append("行业或候选类型与当前科技成长/热点主线存在匹配。")
    if trend_status == "上行":
        reasons.append("趋势状态为上行，价格位于关键均线上方。")
    if signal:
        reasons.append(f"最近策略信号来自「{signal.get('strategy_name')}」，可作为量化观察依据。")
    return reasons[:6] or ["当前看多依据不足，评级主要来自中性观察。"]


def _bearish_reasons(
    rating: str,
    risk_level: str,
    data_confidence: str,
    row: dict,
    data_notes: list[str],
    market_regime: str,
) -> list[str]:
    reasons = []
    if rating in {"减持", "卖出", "无法评级"}:
        reasons.append(f"评级为{rating}，模型优先提示风险约束或数据质量问题。")
    if risk_level != "低":
        reasons.append(f"风险等级为{risk_level}，需要控制仓位和关注优先级。")
    if data_confidence != "高":
        reasons.append(f"数据可信度为{data_confidence}，部分维度需要人工复核。")
    drawdown = safe_float(row.get("max_drawdown_60"))
    volatility = safe_float(row.get("volatility_60"))
    if drawdown > 0.25:
        reasons.append(f"60 日最大回撤约 {drawdown:.1%}，回撤压力偏高。")
    if volatility > 0.35:
        reasons.append(f"60 日波动率约 {volatility:.1%}，短期波动风险偏高。")
    if market_regime in {"RiskOff", "Panic"}:
        reasons.append(f"市场状态为 {market_regime}，系统对积极评级进行约束。")
    reasons.extend(data_notes)
    return reasons[:7] or ["暂未识别到显著看空风险，但仍需人工确认数据与市场状态。"]


def _rating_change_triggers(trend_status: str, market_regime: str) -> tuple[list[str], list[str]]:
    upgrade = [
        "市场状态从 Choppy/RiskOff 转为 Recovery/RiskOn",
        "股价重新站上 MA20 并伴随成交额放大",
        "所属板块进入今日主线或板块热度提升",
        "基本面指标或策略质量分改善",
        "风险等级从中/高降为低",
    ]
    downgrade = [
        "放量跌破 MA20",
        "跌破 MA60 或 MA60 斜率转负",
        "所属板块热度下降或题材退潮",
        "换手率或波动率异常放大",
        "市场状态转为 RiskOff 或 Panic",
        "财务数据恶化或数据可信度下降",
    ]
    if trend_status == "下行":
        upgrade.insert(0, "重新站上 MA20 且 20 日收益转正")
    if market_regime in {"RiskOn", "Recovery"}:
        downgrade.insert(0, "强修复行情未能延续，市场状态回落至 Choppy/RiskOff")
    return upgrade[:6], downgrade[:7]


def _rating_horizon(scores: dict[str, float | None], signal: dict | None) -> str:
    metadata = _signal_metadata(signal)
    candidate_types = metadata.get("candidateTypes") or []
    if any(item in {"热点题材", "短线强势", "龙头候选"} for item in candidate_types):
        return "短期：1-4周"
    if (scores.get("fundamentalScore") or 0) >= max(scores.get("technicalScore") or 0, scores.get("sentimentScore") or 0):
        return "长期：6-12个月"
    return "中期：1-3个月"


def _rating_summary(rating: str, overall_score: float, risk_level: str, data_confidence: str, market_regime: str, reasons: list[str]) -> str:
    reason = reasons[0] if reasons else "评级由五维评分和风险约束生成。"
    return f"给予{rating}评级：综合评分 {overall_score:.1f}，风险等级{risk_level}，数据可信度{data_confidence}，市场状态 {market_regime}。{reason}"


def _analysis_sections(scores: dict[str, float | None], row: dict, signal: dict | None, risk_level: str, data_notes: list[str]) -> dict[str, list[str]]:
    return {
        "fundamental": [
            f"基本面评分：{_score_text(scores.get('fundamentalScore'))}",
            "当前第一版主要使用策略质量和行业代理信息；PE/PB/PS、公告日期财务数据仍需接入后增强。",
        ],
        "technical": [
            f"技术面评分：{_score_text(scores.get('technicalScore'))}",
            f"MA20={_round(row.get('ma20'))}，MA60={_round(row.get('ma60'))}，60日收益={_pct_text(row.get('ret60'))}。",
        ],
        "sentiment": [
            f"情绪面评分：{_score_text(scores.get('sentimentScore'))}",
            f"最近策略信号：{signal.get('strategy_name') if signal else '暂无'}。",
        ],
        "capitalFlow": [
            f"资金面评分：{_score_text(scores.get('capitalFlowScore'))}",
            f"成交额相对20日均值：{_amount_ratio(row) or 0:.2f} 倍。",
        ],
        "risk": [
            f"风险面评分：{_score_text(scores.get('riskControlScore'))}",
            f"风险等级：{risk_level}。60日回撤={_pct_text(row.get('max_drawdown_60'))}，60日波动={_pct_text(row.get('volatility_60'))}。",
            *(data_notes or ["暂无额外数据完整性警告。"]),
        ],
    }


def _invalid_conditions(rating: str, trend_status: str, market_regime: str) -> list[str]:
    if rating == "买入":
        return [
            "市场状态不再维持 RiskOn 或 Recovery",
            "股价放量跌破 MA20",
            "所属板块热度明显下降",
            "风险等级上升至高或数据可信度下降",
        ]
    if rating == "卖出":
        return [
            "重新站上 MA20 且成交额恢复",
            "风险等级下降并且趋势状态不再下行",
            "所属板块重新进入主线并获得策略信号确认",
        ]
    return [
        f"当前趋势为{trend_status}、市场为{market_regime}，评级需随价格、板块热度和风险等级变化重新评估。",
    ]


def _amount_ratio(row: dict) -> float | None:
    amount = safe_float(row.get("amount"))
    amount_ma20 = safe_float(row.get("amount_ma20"))
    if amount <= 0 or amount_ma20 <= 0:
        return None
    return round(amount / amount_ma20, 4)


def _score_text(value: float | None) -> str:
    return "数据不足" if value is None else f"{value:.1f}"


def _pct_text(value: object) -> str:
    number = safe_float(value)
    return f"{number:.1%}"


def _round(value: object, digits: int = 2) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return round(number, digits)


def _json_loads(raw: object, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return default
