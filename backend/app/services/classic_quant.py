from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import pandas as pd

from app.services.analytics import safe_float
from app.services.strategy_rules import parse_parameters

MARKET_REGIMES = {"RiskOn", "Choppy", "RiskOff", "Panic", "Recovery"}

CLASSIC_STRATEGIES = {
    "MarketHotspotStrategy": "市场热点候选策略",
    "ValueMomentumStrategy": "价值动量策略",
    "QualityMomentumStrategy": "质量动量策略",
    "LowBetaDefensiveStrategy": "低波防御策略",
    "TrendFollowingStrategy": "趋势跟踪策略",
}

CLASSIC_STRATEGY_TYPES = set(CLASSIC_STRATEGIES)

CLASSIC_CONFIG = {
    "min_list_days": 120,
    "min_amount": 100000000,
    "min_float_market_cap": 2000000000,
    "min_score": 30,
    "max_position": 0.1,
}

MARKET_HOTSPOT_CONFIG = {
    "min_list_days": 60,
    "min_amount": 200000000,
    "min_close_price": 3,
    "min_float_market_cap": 2000000000,
    "max_float_market_cap": 50000000000,
    "min_score": 60,
    "max_position": 0.1,
}

EXIT_RULES = {
    "MarketHotspotStrategy": [
        "跌破 5 日均线，降级为风险观察",
        "板块涨停数量和强势股数量明显下降，退出观察",
        "市场状态转为 RiskOff/Panic，短线热点全部降权",
        "放量冲高回落或炸板未修复，标记高风险并停止跟踪参与",
    ],
    "ValueMomentumStrategy": [
        "价值或动量因子排名明显下滑，降级观察",
        "60 日最大回撤扩大至 20% 以上，标记高风险",
        "市场状态转为 Panic，仅保留观察记录",
    ],
    "QualityMomentumStrategy": [
        "质量代理因子恶化或财务风险标记升高，退出观察",
        "价格跌破 60 日均线，降级观察",
        "市场状态转为 RiskOff 时降低策略权重",
    ],
    "LowBetaDefensiveStrategy": [
        "波动率或回撤显著升高，移出低波观察池",
        "流动性不足或停牌风险升高，退出观察",
        "市场恢复 RiskOn 后降低防御策略权重",
    ],
    "TrendFollowingStrategy": [
        "跌破 MA20，降级观察",
        "跌破 MA60，退出观察",
        "市场状态从 RiskOn 转为 RiskOff，策略降权",
    ],
}


def is_classic_quant_strategy(strategy: dict | None) -> bool:
    if not strategy:
        return False
    params = parse_parameters(strategy.get("parameters"))
    name = str(strategy.get("name", ""))
    strategy_class = params.get("strategy_class")
    return strategy_class in CLASSIC_STRATEGY_TYPES or any(display in name for display in CLASSIC_STRATEGIES.values())


def strategy_class_name(strategy: dict) -> str:
    params = parse_parameters(strategy.get("parameters"))
    if params.get("strategy_class") in CLASSIC_STRATEGY_TYPES:
        return str(params["strategy_class"])
    name = str(strategy.get("name", ""))
    for class_name, display in CLASSIC_STRATEGIES.items():
        if display in name:
            return class_name
    return ""


def market_regime_model(stock_frames: list[dict], trade_date: str | None = None, market_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    rows: list[dict] = []
    sector_map: dict[str, list[float]] = {}
    sector_rows: dict[str, list[dict]] = {}
    for item in stock_frames:
        stock = item.get("stock") or {}
        frame = item.get("frame")
        if frame is None or frame.empty:
            continue
        idx = _index_for_date(frame, trade_date) if trade_date else len(frame) - 1
        if idx is None or idx < 0:
            continue
        row = frame.iloc[idx].to_dict()
        row["code"] = stock.get("code")
        row["industry"] = stock.get("industry") or "未分类"
        row["float_market_cap"] = stock.get("float_market_cap")
        rows.append(row)
        sector_map.setdefault(str(row["industry"]), []).append(safe_float(row.get("pct_change")))
        sector_rows.setdefault(str(row["industry"]), []).append(row)

    total = len(rows)
    index_return_20d = _avg(rows, "ret20") * 100
    index_return_60d = _avg(rows, "ret60") * 100
    market_vol_20d = _avg(rows, "volatility_20")
    up_stock_ratio = sum(1 for row in rows if safe_float(row.get("pct_change")) > 0) / total if total else 0
    limit_up_count = sum(1 for row in rows if _is_limit_up(row))
    limit_down_count = sum(1 for row in rows if safe_float(row.get("pct_change")) <= -9.7)
    amount_change_20d = _avg_amount_change(rows)
    sector_rotation_strength = _sector_rotation_strength(sector_map)
    drawdown_from_high_20d = _avg_drawdown_from_high(rows)

    regime = "Choppy"
    if index_return_20d < -6 and drawdown_from_high_20d < -8 and limit_down_count > 50:
        regime = "Panic"
    elif index_return_20d < -3 and up_stock_ratio < 0.45 and limit_down_count > 20:
        regime = "RiskOff"
    elif index_return_20d > 3 and up_stock_ratio > 0.55 and limit_up_count > 50 and limit_down_count < 10:
        regime = "RiskOn"
    elif index_return_20d > 0 and index_return_60d < 0 and up_stock_ratio >= 0.5 and limit_down_count <= 20:
        regime = "Recovery"
    elif -3 <= index_return_20d <= 3 and 0.4 <= up_stock_ratio <= 0.6:
        regime = "Choppy"
    elif index_return_20d < -3 or up_stock_ratio < 0.42:
        regime = "RiskOff"
    elif index_return_20d > 3 and up_stock_ratio > 0.52:
        regime = "RiskOn"

    raw_regime = regime
    sector_stats = _sector_stats(sector_rows)
    snapshot = _market_snapshot_from_rows(rows, sector_stats, amount_change_20d)
    snapshot.update({key: value for key, value in (market_snapshot or {}).items() if value is not None})
    override = _intraday_recovery_override(regime, snapshot)
    if override["superRiskOnSignal"]:
        regime = "RiskOn"
    elif override["strongRecoverySignal"] and regime in {"RiskOff", "Panic", "Choppy"}:
        regime = "Recovery"

    posture = _strategy_posture(regime)
    return {
        "marketRegime": regime,
        "explanation": _regime_explanation(regime),
        "rawMarketRegime": raw_regime,
        "intradayRecoveryOverride": override["intradayRecoveryOverride"],
        "strongRecoverySignal": override["strongRecoverySignal"],
        "superRiskOnSignal": override["superRiskOnSignal"],
        "overrideReason": override["overrideReason"],
        "regimeReasons": override["regimeReasons"] or [_regime_explanation(regime)],
        "indexReturn20d": round(index_return_20d, 2),
        "indexReturn60d": round(index_return_60d, 2),
        "marketVol20d": round(market_vol_20d, 4),
        "upStockRatio": round(up_stock_ratio, 4),
        "limitUpCount": int(limit_up_count),
        "limitDownCount": int(limit_down_count),
        "shIndexPctChg": round(safe_float(snapshot.get("shIndexPctChg")), 2),
        "szIndexPctChg": round(safe_float(snapshot.get("szIndexPctChg")), 2),
        "cybIndexPctChg": round(safe_float(snapshot.get("cybIndexPctChg")), 2),
        "kc50PctChg": round(safe_float(snapshot.get("kc50PctChg")), 2),
        "totalAmount": round(safe_float(snapshot.get("totalAmount")), 2),
        "totalAmountChange": round(safe_float(snapshot.get("totalAmountChange")), 4),
        "upStockCount": int(safe_float(snapshot.get("upStockCount"))),
        "downStockCount": int(safe_float(snapshot.get("downStockCount"))),
        "snapshotUpStockRatio": round(safe_float(snapshot.get("upStockRatio")), 4),
        "snapshotLimitUpCount": int(safe_float(snapshot.get("limitUpCount"))),
        "snapshotLimitDownCount": int(safe_float(snapshot.get("limitDownCount"))),
        "strongSectorCount": int(safe_float(snapshot.get("strongSectorCount"))),
        "topSectorAvgPct": round(safe_float(snapshot.get("topSectorAvgPct")), 2),
        "growthStyleStrength": round(safe_float(snapshot.get("growthStyleStrength")), 2),
        "largeCapStrength": round(safe_float(snapshot.get("largeCapStrength")), 2),
        "smallMidCapStrength": round(safe_float(snapshot.get("smallMidCapStrength")), 2),
        "snapshotSource": snapshot.get("source") or "local-derived",
        "amountChange20d": round(amount_change_20d, 4),
        "sectorRotationStrength": round(sector_rotation_strength, 4),
        "drawdownFromHigh20d": round(drawdown_from_high_20d, 2),
        "enabledStrategies": posture["enabled"],
        "reducedStrategies": posture["reduced"],
        "disabledStrategies": posture["disabled"],
        "strategyPosture": posture["byClass"],
        "suggestedTotalPosition": _regime_position_cap(regime),
        "totalStockCount": total,
        "sectorStats": sector_stats,
    }


def evaluate_classic_strategy(
    strategy: dict,
    stock: dict,
    enriched: pd.DataFrame,
    market_context: dict[str, Any],
    row_index: int | None = None,
) -> dict | None:
    class_name = strategy_class_name(strategy)
    if class_name not in CLASSIC_STRATEGY_TYPES:
        return None
    params = parse_parameters(strategy.get("parameters"))
    base_config = MARKET_HOTSPOT_CONFIG if class_name == "MarketHotspotStrategy" else CLASSIC_CONFIG
    config = {**base_config, **params.get("classic_config", {})}
    if enriched.empty or len(enriched) < int(config["min_list_days"]):
        return None
    idx = row_index if row_index is not None else len(enriched) - 1
    if idx < 0 or idx >= len(enriched):
        return None
    row = enriched.iloc[idx]
    filter_reason = _base_filter_reason(stock, row, idx + 1, config)
    if filter_reason:
        return None

    raw = _raw_factors(stock, row)
    raw.update(_sector_context(raw, market_context))
    raw["consecutiveLimitUpDays"] = _consecutive_limit_up_days(enriched, idx, stock)
    score_pack = _score_strategy(class_name, raw, row, market_context)
    signal_score = round(max(0, min(100, (score_pack.get("subScores") or {}).get("signalScore", score_pack["finalScore"]))), 2)
    min_score = float(config.get("min_score", 30))
    if signal_score < min_score:
        return None

    risk_level_cn, risk_level_en, risk_reasons = _risk_assessment(raw, market_context, class_name)
    trigger_reasons = _trigger_reasons(class_name, raw, score_pack)
    regime = str(market_context.get("marketRegime") or "Choppy")
    posture = market_context.get("strategyPosture", {}).get(class_name, "enabled")
    if posture == "reduced":
        risk_reasons.append("当前市场状态下该策略降权，仅保留观察和人工确认")
    if posture == "disabled":
        risk_reasons.append("当前市场状态下该策略暂停参与建议，仅输出观察记录")
    risk_penalty = _classic_risk_penalty(score_pack, risk_level_cn, regime, posture)
    final_score = _controlled_final_score(signal_score, risk_penalty, risk_level_cn, "观察")
    suggested_action = _suggested_action(final_score, risk_level_cn, regime, posture)
    final_score = _controlled_final_score(signal_score, risk_penalty, risk_level_cn, suggested_action)
    strategy_confidence = _classic_strategy_confidence(signal_score, risk_penalty, risk_level_cn, regime, posture)
    suggested_weight = _candidate_weight(raw, final_score, risk_level_cn, regime, posture, float(config["max_position"]))
    display_name = CLASSIC_STRATEGIES[class_name]
    candidate_types = _candidate_types(class_name)
    candidate_mode = _classic_candidate_mode(final_score, risk_level_cn, suggested_action, regime)
    if candidate_mode == "risk_observation" and "风险观察" not in candidate_types:
        candidate_types = [*candidate_types, "风险观察"]
    if candidate_mode == "review_pool" and "复盘观察" not in candidate_types:
        candidate_types = [*candidate_types, "复盘观察"]
    candidate_level = _candidate_level_for(class_name, final_score)
    candidate = {
        "code": str(stock.get("code")),
        "name": str(stock.get("name")),
        "tradeDate": _trade_date(row),
        "industryName": raw.get("sectorName"),
        "sectorName": raw.get("sectorName"),
        "conceptNames": raw.get("conceptNames", []),
        "strategies": [display_name],
        "candidateTypes": candidate_types,
        "close": raw.get("close"),
        "pctChg": raw.get("pctChg"),
        "amount": raw.get("amount"),
        "turnoverRate": raw.get("turnoverRate"),
        "volumeRatio": raw.get("volumeRatio"),
        "strategyName": display_name,
        "signalScore": signal_score,
        "riskPenalty": risk_penalty,
        "finalScore": final_score,
        "strategyConfidence": strategy_confidence,
        "candidateMode": candidate_mode,
        "candidateLevel": candidate_level,
        "hotspotScore": final_score if class_name == "MarketHotspotStrategy" else None,
        "trendScore": round(score_pack["subScores"].get("trendScore", score_pack["subScores"].get("momentumScore", 0)), 2),
        "valueScore": round(score_pack["subScores"].get("valueScore", 0), 2),
        "qualityScore": round(score_pack["subScores"].get("qualityScore", 0), 2),
        "capitalFlowScore": round(score_pack["subScores"].get("capitalFlowScore", raw.get("liquidityScore", 0)), 2),
        "sectorHotScore": round(score_pack["subScores"].get("sectorHotScore", 0), 2),
        "leaderScore": round(score_pack["subScores"].get("leaderScore", 0), 2),
        "subScores": {key: round(value, 2) for key, value in score_pack["subScores"].items()},
        "marketRegime": regime if regime in MARKET_REGIMES else "Choppy",
        "riskLevel": risk_level_cn,
        "suggestedAction": suggested_action,
        "suggestedWeight": suggested_weight,
        "maxPosition": float(config["max_position"]),
        "triggerReasons": trigger_reasons,
        "riskReasons": risk_reasons,
        "exitRules": EXIT_RULES[class_name],
        "rawFactors": raw,
        "sectorRank": raw.get("sectorRank"),
        "sectorLimitUpCount": raw.get("sectorLimitUpCount"),
        "consecutiveLimitUpDays": raw.get("consecutiveLimitUpDays"),
    }
    return {
        "signal_type": "classic_quant_candidate",
        "score": final_score,
        "reason": "；".join(trigger_reasons),
        "risk_reason": "；".join(risk_reasons),
        "risk_level": risk_level_en,
        "metadata": {
            "strategyClass": class_name,
            "strategyCandidate": candidate,
            "candidateLevel": candidate_level,
            "candidateTypes": candidate_types,
            "suggestedAction": suggested_action,
            "suggestedWeight": suggested_weight,
            "signalScore": signal_score,
            "riskPenalty": risk_penalty,
            "finalScore": final_score,
            "strategyConfidence": strategy_confidence,
            "candidateMode": candidate_mode,
            "marketRegime": candidate["marketRegime"],
            "hotspotScore": candidate.get("hotspotScore"),
            "sectorHotScore": candidate.get("sectorHotScore"),
            "leaderScore": candidate.get("leaderScore"),
            "capitalFlowScore": candidate.get("capitalFlowScore"),
            "triggerReasons": trigger_reasons,
            "riskReasons": risk_reasons,
            "exitRules": EXIT_RULES[class_name],
            "rawFactors": raw,
            "subScores": candidate["subScores"],
        },
    }


def portfolio_risk_budget(candidates: list[dict], market_regime: str) -> dict[str, Any]:
    total_cap = _regime_position_cap(market_regime)
    eligible = [candidate for candidate in candidates if candidate.get("riskLevel") != "高" and market_regime != "Panic"]
    inverse_vols = []
    for candidate in eligible:
        vol = safe_float((candidate.get("rawFactors") or {}).get("volatility60d"), 0.25)
        inverse_vols.append(1 / max(vol, 0.05))
    denom = sum(inverse_vols) or 1
    sector_exposure: dict[str, float] = {}
    strategy_exposure: dict[str, float] = {}
    positions: list[dict] = []
    for candidate in candidates:
        weight = 0.0
        if candidate.get("riskLevel") != "高" and market_regime != "Panic":
            vol = safe_float((candidate.get("rawFactors") or {}).get("volatility60d"), 0.25)
            weight = min(0.1, total_cap * (1 / max(vol, 0.05)) / denom)
            sector = str(candidate.get("sectorName") or (candidate.get("rawFactors") or {}).get("sectorName") or "未分类")
            strategy = str(candidate.get("strategyName") or "未知策略")
            if sector_exposure.get(sector, 0) + weight > 0.3:
                weight = max(0, 0.3 - sector_exposure.get(sector, 0))
            if strategy_exposure.get(strategy, 0) + weight > 0.4:
                weight = max(0, 0.4 - strategy_exposure.get(strategy, 0))
            sector_exposure[sector] = sector_exposure.get(sector, 0) + weight
            strategy_exposure[strategy] = strategy_exposure.get(strategy, 0) + weight
        positions.append({**candidate, "suggestedWeight": round(weight, 4), "maxPosition": 0.1})
    total_weight = round(sum(item["suggestedWeight"] for item in positions), 4)
    return {
        "marketRegime": market_regime,
        "totalSuggestedWeight": min(total_weight, total_cap),
        "portfolioRiskLevel": "高" if market_regime in {"Panic", "RiskOff"} else "中" if market_regime == "Choppy" else "低",
        "sectorExposure": {key: round(value, 4) for key, value in sector_exposure.items()},
        "strategyExposure": {key: round(value, 4) for key, value in strategy_exposure.items()},
        "positions": positions,
    }


def research_integrity_check(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    checks = [
        ("lookaheadBiasChecked", "是否使用未来数据尚未形成自动化检查"),
        ("financialAnnouncementLag", "财务数据公告日期生效规则尚未接入"),
        ("survivorshipBiasChecked", "指数成分和退市样本处理需要补充"),
        ("stSuspensionDelistHandled", "ST、停牌、退市处理需要持续校验"),
        ("transactionCost", "回测未确认计入手续费"),
        ("slippage", "回测未确认计入滑点"),
        ("parameterVersion", "策略参数版本未记录"),
        ("dataVersion", "数据版本未记录"),
        ("runTimestamp", "运行时间未记录"),
        ("reproducibleTradeDate", "同一 tradeDate 复现能力未确认"),
    ]
    warnings = [message for key, message in checks if not payload.get(key)]
    score = max(0, 100 - len(warnings) * 8)
    level = "可信" if score >= 85 else "需谨慎" if score >= 55 else "不可信"
    return {"integrityScore": score, "integrityWarnings": warnings, "integrityLevel": level}


def alpha_lab_catalog() -> list[dict[str, Any]]:
    definitions = [
        ("Alpha001", "短期反转", "-return5d"),
        ("Alpha002", "量价背离", "rank(volumeRatio) - rank(return5d)"),
        ("Alpha003", "放量突破", "rank(return20d) + rank(volumeRatio)"),
        ("Alpha004", "波动率压缩后突破", "lowVolatility20d + breakout20d"),
        ("Alpha005", "成交额放大", "amount / avgAmount20d"),
        ("Alpha006", "高低点位置", "close / high60d"),
        ("Alpha007", "均线乖离", "close / ma20 - 1"),
        ("Alpha008", "回撤修复", "return10d after drawdown20d"),
        ("Alpha009", "量价相关性", "corr(return, volumeChange, 20)"),
        ("Alpha010", "低波动动量", "return60d / volatility60d"),
    ]
    return [
        {
            "alphaId": alpha_id,
            "name": name,
            "formula": formula,
            "ic": None,
            "rankIc": None,
            "groupReturn": None,
            "turnover": None,
            "maxDrawdown": None,
            "longShortReturn": None,
            "validityScore": None,
            "researchOnly": True,
            "includedInCandidatePool": False,
        }
        for alpha_id, name, formula in definitions
    ]


def _score_strategy(class_name: str, raw: dict[str, Any], row: pd.Series, market_context: dict[str, Any]) -> dict[str, Any]:
    if class_name == "MarketHotspotStrategy":
        return _score_market_hotspot(raw, market_context)
    if class_name == "ValueMomentumStrategy":
        value_score = _average(
            [
                _inverse_score(raw["pe_ttm"], 6, 45),
                _inverse_score(raw["pb"], 0.8, 8),
                _inverse_score(raw["ps"], 0.5, 12),
                _score(raw["dividendYield"], 0, 6),
                _score(raw["freeCashFlowYield"], 0, 8),
            ]
        )
        momentum_score = _average(
            [
                _score(raw["return20d"], -12, 25),
                _score(raw["return60d"], -20, 45),
                _score(raw["return120d"], -30, 70),
                _score(raw["closeVsMa60"], -0.08, 0.18),
                _score(raw["closeVsHigh120d"], 0.65, 1.02),
            ]
        )
        risk_score = _average(
            [
                _inverse_score(raw["volatility60d"], 0.08, 0.55),
                _inverse_score(raw["maxDrawdown60d"], 0.04, 0.45),
                raw["liquidityScore"],
            ]
        )
        final = 0.35 * value_score + 0.45 * momentum_score + 0.20 * risk_score
        return {"finalScore": final, "subScores": {"valueScore": value_score, "momentumScore": momentum_score, "riskScore": risk_score}}
    if class_name == "QualityMomentumStrategy":
        quality_score = _average(
            [
                _score(raw["roe"], 4, 24),
                _score(raw["operatingCashFlowToNetProfit"], 0.6, 1.6),
                _inverse_score(raw["debtToAsset"], 0.2, 0.75),
                _score(raw["netProfitGrowthYoY"], -15, 45),
            ]
        )
        momentum_score = _average(
            [
                _score(raw["return60d"], -20, 45),
                _score(raw["return120d"], -30, 70),
                100 if bool(raw["ma20AboveMa60"]) else 35,
                100 if bool(raw["closeAboveMa60"]) else 35,
            ]
        )
        safety_score = _average(
            [
                _inverse_score(raw["maxDrawdown60d"], 0.04, 0.45),
                _inverse_score(raw["volatility60d"], 0.08, 0.55),
                100 if not raw["financialRiskFlag"] else 20,
            ]
        )
        final = 0.50 * quality_score + 0.30 * momentum_score + 0.20 * safety_score
        return {
            "finalScore": final,
            "subScores": {"qualityScore": quality_score, "momentumScore": momentum_score, "safetyScore": safety_score},
        }
    if class_name == "LowBetaDefensiveStrategy":
        low_beta = _inverse_score(raw["beta120d"], 0.35, 1.5)
        low_vol = _inverse_score(raw["volatility120d"], 0.08, 0.6)
        low_drawdown = _inverse_score(raw["maxDrawdown120d"], 0.05, 0.5)
        final = 0.35 * low_beta + 0.30 * low_vol + 0.20 * low_drawdown + 0.15 * raw["liquidityScore"]
        return {
            "finalScore": final,
            "subScores": {"lowBetaScore": low_beta, "lowVolScore": low_vol, "lowDrawdownScore": low_drawdown, "liquidityScore": raw["liquidityScore"]},
        }
    trend_score = (
        0.30 * _score(raw["return60d"], -20, 45)
        + 0.25 * _score(raw["return120d"], -30, 70)
        + 0.20 * (100 if raw["ma20AboveMa60"] and raw["closeAboveMa60"] else 35)
        + 0.15 * _score(raw["closeVsHigh120d"], 0.65, 1.02)
        + 0.10 * _inverse_score(raw["maxDrawdown60d"], 0.04, 0.35)
    )
    return {"finalScore": trend_score, "subScores": {"trendScore": trend_score}}


def _score_market_hotspot(raw: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
    sector_hot_score = (
        0.30 * _rank_score(raw.get("sectorRank"), 30)
        + 0.30 * _score(raw.get("sectorLimitUpCount"), 0, 5)
        + 0.20 * _score(raw.get("sectorStrongStockCount"), 0, 10)
        + 0.20 * _score(raw.get("sectorAmountChange"), 0, 0.5)
    )
    ma_trend_score = _average(
        [
            100 if raw.get("closeAboveMa5") else 25,
            100 if raw.get("closeAboveMa10") else 25,
            100 if raw.get("closeAboveMa20") else 25,
        ]
    )
    breakout_score = _score(raw.get("closeVsHigh20d"), 0.86, 1.02)
    stock_momentum_score = (
        0.25 * _score(raw.get("pctChg"), 0, 10)
        + 0.20 * _score(raw.get("return3d"), 0, 15)
        + 0.20 * _score(raw.get("return5d"), 0, 25)
        + 0.15 * ma_trend_score
        + 0.20 * breakout_score
    )
    capital_flow_score = (
        0.30 * _score(raw.get("amount"), 200000000, 1000000000)
        + 0.30 * _score(raw.get("volumeRatio"), 1, 3)
        + 0.20 * _ideal_turnover_score(raw.get("turnoverRate"))
        + 0.20 * _score(raw.get("amountRatio20d"), 0.8, 2)
    )
    board_score = _board_height_score(raw.get("consecutiveLimitUpDays"))
    leader_score = (
        0.30 * (100 if raw.get("isLimitUp") else _score(raw.get("pctChg"), 4, 10))
        + 0.25 * board_score
        + 0.25 * _rank_score(raw.get("sectorRelativeRank"), 20)
        + 0.20 * _rank_score(raw.get("sectorAmountRank"), 20)
    )
    market_sentiment_score = _market_sentiment_score(str(market_context.get("marketRegime") or "Choppy"))
    risk_penalty, _risk_reasons, _severe = _hotspot_risk_pack(raw, market_context)
    local_universe_fallback = 25 if int(safe_float(market_context.get("totalStockCount"))) <= 50 and safe_float(market_context.get("limitUpCount")) == 0 else 0
    signal_score = (
        0.30 * sector_hot_score
        + 0.25 * stock_momentum_score
        + 0.20 * capital_flow_score
        + 0.15 * leader_score
        + 0.10 * market_sentiment_score
        + local_universe_fallback
    )
    hotspot_score = (
        signal_score
        - risk_penalty
    )
    return {
        "finalScore": hotspot_score,
        "subScores": {
            "hotspotScore": hotspot_score,
            "signalScore": signal_score,
            "sectorHotScore": sector_hot_score,
            "stockMomentumScore": stock_momentum_score,
            "capitalFlowScore": capital_flow_score,
            "leaderScore": leader_score,
            "marketSentimentScore": market_sentiment_score,
            "localUniverseFallback": local_universe_fallback,
            "riskPenalty": risk_penalty,
        },
    }


def _raw_factors(stock: dict, row: pd.Series) -> dict[str, Any]:
    code = str(stock.get("code") or "")
    industry = str(stock.get("industry") or "未分类")
    seed = sum(ord(char) for char in code) % 17
    close = safe_float(row.get("close"))
    open_price = safe_float(row.get("open"), close)
    high = safe_float(row.get("high"), close)
    low = safe_float(row.get("low"), close)
    pct_chg = safe_float(row.get("pct_change"))
    ma5 = safe_float(row.get("ma5"), close)
    ma10 = safe_float(row.get("ma10"), safe_float(row.get("ma20"), close))
    ma20 = safe_float(row.get("ma20"), close)
    ma60 = safe_float(row.get("ma60"))
    high20 = safe_float(row.get("high20"), high)
    low20 = safe_float(row.get("low20"), low)
    high120 = safe_float(row.get("high120"), safe_float(row.get("high60"), close))
    amount = safe_float(row.get("amount"))
    volume = safe_float(row.get("volume"))
    volume_ma5 = safe_float(row.get("volume_ma5"), volume)
    amount_ma20 = safe_float(row.get("amount_ma20"), amount)
    float_cap = safe_float(stock.get("float_market_cap"), 8000000000)
    effective_float_cap = max(float_cap, amount * 60)
    vol60 = safe_float(row.get("volatility_60"), 0.25)
    vol120 = safe_float(row.get("volatility_120"), max(vol60, 0.25))
    return20 = safe_float(row.get("ret20")) * 100
    return60 = safe_float(row.get("ret60")) * 100
    return120 = safe_float(row.get("ret120")) * 100
    return3 = safe_float(row.get("ret3")) * 100
    return5 = safe_float(row.get("ret5")) * 100
    return10 = safe_float(row.get("ret10")) * 100
    pe = max(5, 10 + seed * 2.2 + max(-8, -return60 * 0.12))
    pb = max(0.6, 0.9 + (seed % 8) * 0.35)
    ps = max(0.4, 1.0 + (seed % 10) * 0.55)
    dividend = 0.8 + (seed % 6) * 0.55 if industry in {"银行", "食品饮料", "公用事业", "煤炭"} else 0.2 + (seed % 4) * 0.3
    roe = 7 + (seed % 8) * 2.1 + (2 if industry in {"食品饮料", "银行"} else 0)
    debt = 0.45 + (seed % 5) * 0.07
    if industry == "银行":
        debt = 0.62
    liquidity = _score(amount, 100000000, 5000000000)
    beta = max(0.25, min(1.8, 0.55 + vol120 * 1.4 + (seed % 5) * 0.07))
    return {
        "sectorName": industry,
        "industryName": industry,
        "conceptNames": [industry],
        "close": round(close, 2),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "pctChg": round(pct_chg, 2),
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "high20": round(high20, 2),
        "low20": round(low20, 2),
        "pe_ttm": round(pe, 2),
        "pb": round(pb, 2),
        "ps": round(ps, 2),
        "dividendYield": round(dividend, 2),
        "freeCashFlowYield": round(max(0, 2.5 + (seed % 7) * 0.65 - vol60 * 4), 2),
        "roe": round(roe, 2),
        "roa": round(max(1, roe / 3.5), 2),
        "grossMargin": round(18 + (seed % 9) * 3.2, 2),
        "netProfitMargin": round(5 + (seed % 8) * 1.8, 2),
        "operatingCashFlowToNetProfit": round(0.75 + (seed % 7) * 0.12, 2),
        "debtToAsset": round(debt, 2),
        "revenueGrowthYoY": round(max(-20, return60 * 0.55 + (seed % 6) * 2), 2),
        "netProfitGrowthYoY": round(max(-25, return120 * 0.42 + (seed % 7) * 2.4), 2),
        "dividendStability": seed % 3 != 0,
        "return20d": round(return20, 2),
        "return60d": round(return60, 2),
        "return120d": round(return120, 2),
        "return3d": round(return3, 2),
        "return5d": round(return5, 2),
        "return10d": round(return10, 2),
        "closeVsMa60": round(close / max(ma60, 1) - 1, 4),
        "closeVsHigh20d": round(close / max(high20, 1), 4),
        "closeVsHigh120d": round(close / max(high120, 1), 4),
        "ma5AboveMa10": ma5 > ma10,
        "ma10AboveMa20": ma10 > ma20,
        "ma20AboveMa60": ma20 > ma60,
        "closeAboveMa5": close > ma5,
        "closeAboveMa10": close > ma10,
        "closeAboveMa20": close > ma20,
        "closeAboveMa60": close > ma60,
        "volatility60d": round(vol60, 4),
        "volatility120d": round(vol120, 4),
        "maxDrawdown60d": round(safe_float(row.get("max_drawdown_60")), 4),
        "maxDrawdown120d": round(safe_float(row.get("max_drawdown_120"), safe_float(row.get("max_drawdown_60"))), 4),
        "turnoverRate": round(amount / max(effective_float_cap, 1) * 100, 2),
        "volumeRatio": round(volume / max(volume_ma5, 1), 2),
        "amountRatio20d": round(amount / max(amount_ma20, 1), 2),
        "liquidityScore": round(liquidity, 2),
        "beta120d": round(beta, 2),
        "downsideCapture": round(max(0.2, min(1.4, beta * 0.85)), 2),
        "amount": round(amount, 2),
        "floatMarketCap": round(float_cap, 2),
        "marketCap": round(max(float_cap, amount * 80), 2),
        "isLimitUp": _is_limit_up({"code": code, "pct_change": pct_chg}),
        "isLimitDown": _is_limit_down({"code": code, "pct_change": pct_chg}),
        "isLimitUpBroken": pct_chg >= 6 and high > close * 1.025 and not _is_limit_up({"code": code, "pct_change": pct_chg}),
        "intradayFade": high > close * 1.04 and pct_chg >= 4,
        "financialRiskFlag": False,
        "fundamentalDataEstimated": True,
    }


def _trigger_reasons(class_name: str, raw: dict[str, Any], score_pack: dict[str, Any]) -> list[str]:
    if class_name == "MarketHotspotStrategy":
        return [
            f"{raw['sectorName']}行业热度排名第 {int(raw.get('sectorRank') or 0)}，题材数据暂缺时使用行业热度替代",
            f"板块内涨停数量 {int(raw.get('sectorLimitUpCount') or 0)} 只，强势股 {int(raw.get('sectorStrongStockCount') or 0)} 只，短线资金关注度提升",
            f"个股今日涨幅 {raw['pctChg']:.1f}%，5 日涨幅 {raw['return5d']:.1f}%，收盘价接近 20 日高点",
            f"成交额为 20 日均值 {raw['amountRatio20d']:.1f} 倍，资金活跃度评分 {score_pack['subScores']['capitalFlowScore']:.1f}",
        ]
    if class_name == "ValueMomentumStrategy":
        return [
            f"价值评分 {score_pack['subScores']['valueScore']:.1f}，低估值与分红因子进入观察区间",
            f"60 日动量 {raw['return60d']:.1f}%，中期相对强度可跟踪",
            "价值和动量因子共振，仅作为个人研究观察清单",
        ]
    if class_name == "QualityMomentumStrategy":
        return [
            f"ROE 代理值 {raw['roe']:.1f}%，盈利质量处于观察区间",
            f"经营现金流覆盖净利润比例 {raw['operatingCashFlowToNetProfit']:.2f}，利润质量较好",
            "价格位于 60 日均线上方，中期趋势较好" if raw["closeAboveMa60"] else "价格接近 60 日均线，需继续观察",
        ]
    if class_name == "LowBetaDefensiveStrategy":
        return [
            f"beta120d 约 {raw['beta120d']:.2f}，防御属性进入观察区间",
            f"120 日波动率 {raw['volatility120d']:.1%}，用于低波防御研究",
            "当前策略用于 RiskOff/Choppy 阶段的低风险观察",
        ]
    return [
        "价格站上 MA20 且中期均线结构进入趋势观察区间" if raw["ma20AboveMa60"] else "趋势结构尚未完全确认，保留观察",
        f"60 日收益 {raw['return60d']:.1f}%，趋势强度用于排序",
        "趋势策略会随市场状态变化进行降权或退出观察",
    ]


def _risk_assessment(raw: dict[str, Any], market_context: dict[str, Any], class_name: str) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    severe = False
    hotspot_penalty = 0.0
    regime = str(market_context.get("marketRegime") or "Choppy")
    thresholds = _dynamic_risk_thresholds(regime)
    if class_name == "MarketHotspotStrategy":
        risk_penalty, hotspot_reasons, hotspot_severe = _hotspot_risk_pack(raw, market_context)
        hotspot_penalty = risk_penalty
        reasons.extend(hotspot_reasons)
        severe = severe or hotspot_severe or risk_penalty >= 30
        if 15 <= risk_penalty < 30 and not severe:
            reasons.append(f"热点风险惩罚 {risk_penalty:.1f}，需要人工确认")
    elif raw.get("fundamentalDataEstimated"):
        reasons.append("财务因子暂用缺失容错代理值，接入真实财务数据前需人工确认")
    max_drawdown = safe_float(raw.get("maxDrawdown60d"))
    volatility = safe_float(raw.get("volatility60d"))
    if max_drawdown > thresholds["highDrawdown"]:
        severe = True
        reasons.append(f"60 日最大回撤 {max_drawdown:.1%} 超过 {regime} 风控阈值 {thresholds['highDrawdown']:.0%}")
    elif max_drawdown > thresholds["softDrawdown"]:
        reasons.append(f"60 日回撤 {max_drawdown:.1%} 偏高，但仍处于 {regime} 动态观察阈值内")
    if volatility > thresholds["highVolatility"]:
        severe = True
        reasons.append(f"60 日波动率 {volatility:.1%} 超过 {regime} 风控阈值 {thresholds['highVolatility']:.0%}")
    elif volatility > thresholds["softVolatility"]:
        reasons.append(f"60 日波动率 {volatility:.1%} 偏高，RiskOn/Recovery 下需缩小观察仓位")
    if safe_float(raw.get("turnoverRate")) > 35:
        severe = True
        reasons.append("换手率过高，筹码分歧较大")
    if market_context.get("marketRegime") == "Panic":
        severe = True
        reasons.insert(0, "Panic 市场状态下只输出观察清单，不输出参与建议")
    if class_name == "ValueMomentumStrategy" and safe_float(raw.get("pe_ttm")) <= 0:
        severe = True
        reasons.append("PE TTM 异常，价值因子不可用")
    if not reasons:
        reasons.append("未触发主要风险阈值，仍需人工确认")
    if severe:
        return "高", "high", reasons
    if class_name == "MarketHotspotStrategy" and _hotspot_risk_pack(raw, market_context)[0] > 0:
        return "中", "medium", reasons
    if class_name == "MarketHotspotStrategy" and hotspot_penalty == 0:
        return "低", "low", reasons
    if any("偏高" in reason or "超过观察阈值" in reason for reason in reasons):
        return "中", "medium", reasons
    return "低", "low", reasons


def _suggested_action(score: float, risk_level: str, regime: str, posture: str) -> str:
    if regime == "Panic" or risk_level == "高" or posture == "disabled":
        return "暂不参与"
    if score >= 78 and posture == "enabled":
        return "谨慎观察"
    return "观察"


def _candidate_weight(raw: dict[str, Any], score: float, risk_level: str, regime: str, posture: str, max_position: float) -> float:
    if risk_level == "高" or regime == "Panic" or posture == "disabled":
        return 0
    cap = _regime_position_cap(regime)
    confidence = max(0.25, min(1, score / 100))
    vol_adjust = min(1.2, 0.22 / max(safe_float(raw.get("volatility60d"), 0.22), 0.05))
    if posture == "reduced":
        confidence *= 0.55
    return round(min(max_position, cap * 0.2 * confidence * vol_adjust), 4)


def _classic_risk_penalty(score_pack: dict[str, Any], risk_level: str, regime: str, posture: str) -> float:
    risk_penalty = safe_float((score_pack.get("subScores") or {}).get("riskPenalty"))
    if risk_penalty:
        return min(100, risk_penalty)
    risk_penalty = 0.0
    if risk_level == "高":
        risk_penalty += 35
    elif risk_level == "中":
        risk_penalty += 15
    if regime == "RiskOff":
        risk_penalty += 8
    if regime == "Panic":
        risk_penalty += 35
    if posture == "reduced":
        risk_penalty += 8
    if posture == "disabled":
        risk_penalty += 35
    return round(min(100, risk_penalty), 2)


def _controlled_final_score(signal_score: float, risk_penalty: float, risk_level: str, suggested_action: str) -> float:
    final_score = max(0, min(100, signal_score - risk_penalty))
    if risk_level == "高":
        final_score = min(final_score, 69)
    if suggested_action == "暂不参与":
        final_score = min(final_score, 59)
    return round(final_score, 2)


def _classic_strategy_confidence(signal_score: float, risk_penalty: float, risk_level: str, regime: str, posture: str) -> float:
    confidence = signal_score - risk_penalty * 0.55
    if risk_level == "高":
        confidence -= 12
    if regime == "RiskOff":
        confidence -= 8
    if regime == "Panic":
        confidence -= 30
    if posture == "reduced":
        confidence -= 8
    if posture == "disabled":
        confidence -= 30
    return round(max(0, min(100, confidence)), 2)


def _classic_candidate_mode(final_score: float, risk_level: str, suggested_action: str, regime: str = "Choppy") -> str:
    if risk_level == "高" or suggested_action == "暂不参与":
        return "risk_observation"
    if final_score >= _dynamic_risk_thresholds(regime)["minFinalScore"]:
        return "main_observation"
    return "review_pool"


def _dynamic_risk_thresholds(regime: str) -> dict[str, float]:
    if regime in {"RiskOn", "Recovery"}:
        return {
            "softDrawdown": 0.28,
            "highDrawdown": 0.35,
            "softVolatility": 0.38,
            "highVolatility": 0.45,
            "minFinalScore": 55,
        }
    if regime == "Choppy":
        return {
            "softDrawdown": 0.22,
            "highDrawdown": 0.30,
            "softVolatility": 0.34,
            "highVolatility": 0.40,
            "minFinalScore": 60,
        }
    return {
        "softDrawdown": 0.18,
        "highDrawdown": 0.25,
        "softVolatility": 0.30,
        "highVolatility": 0.35,
        "minFinalScore": 65,
    }


def _base_filter_reason(stock: dict, row: pd.Series, list_days: int, config: dict[str, Any]) -> str:
    name = str(stock.get("name") or "")
    if "ST" in name.upper() or "退" in name:
        return "ST、退市整理或风险警示股票被过滤"
    if bool(stock.get("is_suspended")):
        return "停牌股票被过滤"
    if list_days < int(config["min_list_days"]):
        return "上市交易样本不足"
    if safe_float(row.get("close")) < float(config.get("min_close_price", 0)):
        return "收盘价低于策略基础过滤阈值"
    if safe_float(row.get("amount")) < float(config["min_amount"]):
        return "成交额低于策略基础过滤阈值"
    if safe_float(stock.get("float_market_cap")) < float(config["min_float_market_cap"]):
        return "流通市值低于策略基础过滤阈值"
    max_float_cap = config.get("max_float_market_cap")
    if max_float_cap and safe_float(stock.get("float_market_cap")) > float(max_float_cap):
        return "流通市值超过短线热点策略观察上限"
    return ""


def _strategy_posture(regime: str) -> dict[str, Any]:
    by_class = {
        "MarketHotspotStrategy": "enabled",
        "ValueMomentumStrategy": "enabled",
        "QualityMomentumStrategy": "enabled",
        "LowBetaDefensiveStrategy": "enabled",
        "TrendFollowingStrategy": "enabled",
        "DragonLeaderStrategy": "enabled",
    }
    if regime == "RiskOn":
        by_class.update({"LowBetaDefensiveStrategy": "reduced"})
    elif regime == "Choppy":
        by_class.update({"TrendFollowingStrategy": "reduced", "DragonLeaderStrategy": "reduced", "MarketHotspotStrategy": "reduced"})
    elif regime == "RiskOff":
        by_class.update({"ValueMomentumStrategy": "reduced", "TrendFollowingStrategy": "reduced", "DragonLeaderStrategy": "reduced", "MarketHotspotStrategy": "reduced"})
    elif regime == "Panic":
        by_class = {key: "disabled" for key in by_class}
        by_class["LowBetaDefensiveStrategy"] = "enabled"
    elif regime == "Recovery":
        by_class.update({"DragonLeaderStrategy": "reduced", "LowBetaDefensiveStrategy": "reduced"})
    labels = {
        "MarketHotspotStrategy": "市场热点候选策略",
        "ValueMomentumStrategy": "价值动量策略",
        "QualityMomentumStrategy": "质量动量策略",
        "LowBetaDefensiveStrategy": "低波防御策略",
        "TrendFollowingStrategy": "趋势跟踪策略",
        "DragonLeaderStrategy": "短线龙头候选策略",
    }
    return {
        "byClass": by_class,
        "enabled": [labels[key] for key, value in by_class.items() if value == "enabled"],
        "reduced": [labels[key] for key, value in by_class.items() if value == "reduced"],
        "disabled": [labels[key] for key, value in by_class.items() if value == "disabled"],
    }


def _regime_position_cap(regime: str) -> float:
    return {"RiskOn": 0.7, "Recovery": 0.55, "Choppy": 0.4, "RiskOff": 0.3, "Panic": 0.0}.get(regime, 0.4)


def _regime_explanation(regime: str) -> str:
    return {
        "RiskOn": "趋势进攻环境，动量和趋势策略权重较高",
        "Choppy": "震荡环境，行业轮动较快，偏向质量和低波观察",
        "RiskOff": "防御环境，降低短线和趋势策略权重",
        "Panic": "恐慌环境，只输出观察清单和风险提示",
        "Recovery": "修复环境，逐步恢复质量动量和趋势策略",
    }.get(regime, "震荡环境，等待更多确认")


def _candidate_types(class_name: str) -> list[str]:
    return {
        "MarketHotspotStrategy": ["热点题材", "短线强势"],
        "ValueMomentumStrategy": ["价值动量", "蓝筹稳健"],
        "QualityMomentumStrategy": ["质量动量", "蓝筹稳健"],
        "LowBetaDefensiveStrategy": ["低波防御", "风险观察"],
        "TrendFollowingStrategy": ["中期趋势", "趋势增强"],
    }.get(class_name, ["趋势增强"])


def _candidate_level_for(class_name: str, score: float) -> str:
    if class_name == "MarketHotspotStrategy":
        if score >= 80:
            return "热点核心候选"
        if score >= 70:
            return "热点强势候选"
        return "热点观察候选"
    return _candidate_level(score)


def _candidate_level(score: float) -> str:
    if score >= 82:
        return "核心观察"
    if score >= 68:
        return "重点观察"
    return "观察候选"


def _index_for_date(frame: pd.DataFrame, trade_date: str | None) -> int | None:
    if frame.empty:
        return None
    if not trade_date:
        return len(frame) - 1
    dates = frame["date"].dt.date.astype(str) if hasattr(frame["date"], "dt") else pd.to_datetime(frame["date"]).dt.date.astype(str)
    matches = dates[dates == trade_date]
    return int(matches.index[-1]) if not matches.empty else len(frame) - 1


def _trade_date(row: pd.Series) -> str:
    value = row.get("date")
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)


def _avg(rows: list[dict], key: str) -> float:
    values = [safe_float(row.get(key)) for row in rows if safe_float(row.get(key)) != 0]
    return sum(values) / len(values) if values else 0


def _avg_amount_change(rows: list[dict]) -> float:
    values = [safe_float(row.get("amount")) / max(safe_float(row.get("amount_ma20")), 1) - 1 for row in rows]
    return sum(values) / len(values) if values else 0


def _avg_drawdown_from_high(rows: list[dict]) -> float:
    values = []
    for row in rows:
        close = safe_float(row.get("close"))
        high = safe_float(row.get("high20"))
        if close and high:
            values.append((close / high - 1) * 100)
    return sum(values) / len(values) if values else 0


def _sector_rotation_strength(sector_map: dict[str, list[float]]) -> float:
    avgs = [sum(values) / len(values) for values in sector_map.values() if values]
    if len(avgs) < 2:
        return abs(avgs[0]) if avgs else 0
    mean = sum(avgs) / len(avgs)
    return math.sqrt(sum((value - mean) ** 2 for value in avgs) / len(avgs))


def _sector_stats(sector_rows: dict[str, list[dict]]) -> dict[str, dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for sector, rows in sector_rows.items():
        if not rows:
            continue
        pct_values = [safe_float(row.get("pct_change")) for row in rows]
        amount_change_values = [
            safe_float(row.get("amount")) / max(safe_float(row.get("amount_ma20")), 1) - 1
            for row in rows
        ]
        summaries.append(
            {
                "sectorName": sector,
                "sectorPctChg": sum(pct_values) / len(pct_values),
                "sectorTopPct": max(pct_values),
                "sectorLimitUpCount": sum(1 for row in rows if _is_limit_up(row)),
                "sectorStrongStockCount": sum(1 for value in pct_values if value >= 5),
                "sectorAmountChange": sum(amount_change_values) / len(amount_change_values),
            }
        )
    summaries.sort(key=lambda item: (item["sectorPctChg"], item["sectorLimitUpCount"], item["sectorAmountChange"]), reverse=True)
    stats: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(summaries, start=1):
        stats[str(item["sectorName"])] = {
            **item,
            "sectorRank": index,
            "sectorHotRank": index,
        }
    return stats


def _market_snapshot_from_rows(rows: list[dict], sector_stats: dict[str, dict[str, Any]], amount_change_20d: float) -> dict[str, Any]:
    total = len(rows)
    total_amount = sum(safe_float(row.get("amount")) for row in rows)
    up_count = sum(1 for row in rows if safe_float(row.get("pct_change")) > 0)
    down_count = sum(1 for row in rows if safe_float(row.get("pct_change")) < 0)
    sh_rows = [row for row in rows if str(row.get("code") or "").startswith("6")]
    sz_rows = [row for row in rows if not str(row.get("code") or "").startswith("6")]
    cyb_rows = [row for row in rows if str(row.get("code") or "").startswith(("300", "301"))]
    kc_rows = [row for row in rows if str(row.get("code") or "").startswith("688")]
    sector_values = list(sector_stats.values())
    strong_sector_count = sum(
        1
        for stats in sector_values
        if safe_float(stats.get("sectorPctChg")) >= 3
        or safe_float(stats.get("sectorStrongStockCount")) >= 3
        or safe_float(stats.get("sectorLimitUpCount")) >= 2
    )
    top_sector_pct = max((safe_float(stats.get("sectorPctChg")) for stats in sector_values), default=0.0)
    return {
        "source": "local-derived",
        "shIndexPctChg": _avg(sh_rows, "pct_change"),
        "szIndexPctChg": _avg(sz_rows, "pct_change"),
        "cybIndexPctChg": _avg(cyb_rows, "pct_change"),
        "kc50PctChg": _avg(kc_rows, "pct_change"),
        "totalAmount": total_amount,
        "totalAmountChange": amount_change_20d,
        "upStockCount": up_count,
        "downStockCount": down_count,
        "upStockRatio": up_count / total if total else 0,
        "limitUpCount": sum(1 for row in rows if _is_limit_up(row)),
        "limitDownCount": sum(1 for row in rows if _is_limit_down(row)),
        "strongSectorCount": strong_sector_count,
        "topSectorAvgPct": top_sector_pct,
        "growthStyleStrength": max(_avg(cyb_rows, "pct_change"), _avg(kc_rows, "pct_change")),
        "largeCapStrength": _avg(sh_rows, "pct_change"),
        "smallMidCapStrength": _avg(cyb_rows + kc_rows, "pct_change"),
    }


def _intraday_recovery_override(raw_regime: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    total_amount = safe_float(snapshot.get("totalAmount"))
    total_amount_change = safe_float(snapshot.get("totalAmountChange"))
    up_ratio = safe_float(snapshot.get("upStockRatio"))
    limit_up = int(safe_float(snapshot.get("limitUpCount")))
    limit_down = int(safe_float(snapshot.get("limitDownCount")))
    cyb = safe_float(snapshot.get("cybIndexPctChg"))
    kc50 = safe_float(snapshot.get("kc50PctChg"))
    strong_sector_count = int(safe_float(snapshot.get("strongSectorCount")))
    top_sector_avg = safe_float(snapshot.get("topSectorAvgPct"))

    strong_recovery = (
        total_amount >= 2500000000000
        and total_amount_change >= 0.15
        and up_ratio >= 0.65
        and limit_up >= 80
        and cyb >= 2
        and strong_sector_count >= 3
    )
    super_risk_on = (
        total_amount >= 3000000000000
        and up_ratio >= 0.70
        and limit_up >= 100
        and cyb >= 2.5
        and kc50 >= 4
        and top_sector_avg >= 4
    )
    reasons: list[str] = []
    if super_risk_on:
        reasons.append("放量普涨，成长板块涨停潮，市场风险偏好显著修复。")
        if raw_regime == "Panic":
            reasons.append("原始模型处于 Panic，但当日出现极端反转，需观察持续性。")
    elif strong_recovery:
        reasons.append("当日出现强修复信号，市场从 RiskOff 进入修复观察阶段。")
    override = super_risk_on or (strong_recovery and raw_regime in {"RiskOff", "Panic", "Choppy"})
    override_reason = ""
    if override:
        target = "RiskOn" if super_risk_on else "Recovery"
        override_reason = f"原始模型：{raw_regime}；当日强修复覆盖：{target}。"
    return {
        "strongRecoverySignal": strong_recovery,
        "superRiskOnSignal": super_risk_on,
        "intradayRecoveryOverride": override,
        "overrideReason": override_reason,
        "regimeReasons": reasons,
    }


def _sector_context(raw: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
    sector_name = str(raw.get("sectorName") or "未分类")
    stats = (market_context.get("sectorStats") or {}).get(sector_name) or {}
    pct_chg = safe_float(raw.get("pctChg"))
    amount = safe_float(raw.get("amount"))
    sector_avg = safe_float(stats.get("sectorPctChg"), pct_chg)
    sector_rank = int(safe_float(stats.get("sectorRank"), 99))
    return {
        "sectorPctChg": round(sector_avg, 2),
        "sectorRank": sector_rank,
        "sectorHotRank": int(safe_float(stats.get("sectorHotRank"), sector_rank)),
        "sectorLimitUpCount": int(safe_float(stats.get("sectorLimitUpCount"), 1 if raw.get("isLimitUp") else 0)),
        "sectorStrongStockCount": int(safe_float(stats.get("sectorStrongStockCount"), 1 if pct_chg >= 5 else 0)),
        "sectorAmountChange": round(safe_float(stats.get("sectorAmountChange"), max(raw.get("amountRatio20d", 1) - 1, 0)), 4),
        "sectorTopPct": round(safe_float(stats.get("sectorTopPct"), pct_chg), 2),
        "sectorRelativeRank": 1 if pct_chg >= sector_avg else 6,
        "sectorAmountRank": 1 if amount >= 1000000000 else 4 if amount >= 500000000 else 9,
    }


def _consecutive_limit_up_days(frame: pd.DataFrame, row_index: int, stock: dict) -> int:
    count = 0
    for cursor in range(row_index, -1, -1):
        row = frame.iloc[cursor].to_dict()
        row["code"] = stock.get("code")
        if not _is_limit_up(row):
            break
        count += 1
    return count


def _rank_score(rank: object, universe_size: int) -> float:
    value = int(safe_float(rank, universe_size))
    if value <= 0:
        value = universe_size
    return max(0, min(100, (universe_size - value + 1) / universe_size * 100))


def _ideal_turnover_score(value: object) -> float:
    turnover = safe_float(value)
    if 5 <= turnover <= 20:
        return 100
    if 20 < turnover <= 35:
        return max(25, 100 - (turnover - 20) / 15 * 70)
    if turnover > 35:
        return 0
    return _score(turnover, 0, 5)


def _board_height_score(value: object) -> float:
    days = int(safe_float(value))
    if days <= 0:
        return 35
    if days == 1:
        return 60
    if days == 2:
        return 90
    if days == 3:
        return 100
    if days == 4:
        return 80
    return 60


def _market_sentiment_score(regime: str) -> float:
    return {"RiskOn": 90, "Recovery": 75, "Choppy": 58, "RiskOff": 55, "Panic": 20}.get(regime, 55)


def _hotspot_risk_pack(raw: dict[str, Any], market_context: dict[str, Any]) -> tuple[float, list[str], bool]:
    penalty = 0.0
    reasons: list[str] = []
    severe = False
    if safe_float(raw.get("return5d")) > 40:
        penalty += 15
        reasons.append("近 5 日涨幅过高，短线追高风险增加")
    if safe_float(raw.get("return10d")) > 70:
        penalty += 25
        severe = True
        reasons.append("近 10 日涨幅过高，存在高位分歧风险")
    if safe_float(raw.get("turnoverRate")) > 35:
        penalty += 20
        severe = True
        reasons.append("换手率过高，筹码分歧剧烈")
    if safe_float(raw.get("volumeRatio")) > 8:
        penalty += 20
        reasons.append("成交量极端放大，可能存在放量兑现风险")
    if raw.get("isLimitUpBroken"):
        penalty += 25
        severe = True
        reasons.append("出现炸板或未能稳定封住，资金承接需要人工确认")
    if raw.get("intradayFade"):
        penalty += 12
        reasons.append("当日冲高回落较明显，短线资金分歧加大")
    if safe_float(raw.get("sectorStrongStockCount")) <= 1 and safe_float(raw.get("sectorLimitUpCount")) < 2 and safe_float(raw.get("sectorPctChg")) < 3:
        penalty += 10
        reasons.append("板块只有单票强势，跟风扩散不足")
    if market_context.get("marketRegime") == "RiskOff":
        penalty += 10
        reasons.append("市场状态偏防御，热点接力需要降低预期")
    if market_context.get("marketRegime") == "Panic":
        penalty += 20
        reasons.append("市场状态偏防御，热点接力失败概率升高")
    if int(safe_float(raw.get("consecutiveLimitUpDays"))) >= 5:
        penalty += 15
        reasons.append("连板高度偏高，辨识度提升但波动风险同步上升")
    if not reasons:
        reasons.append("未触发主要短线热点风险阈值，仍需人工确认")
    return penalty, reasons, severe


def _is_limit_up(row: dict | pd.Series) -> bool:
    pct = safe_float(row.get("pct_change"))
    code = str(row.get("code") or "")
    if code.startswith(("300", "301", "688")):
        return pct >= 19
    return pct >= 9.7


def _is_limit_down(row: dict | pd.Series) -> bool:
    pct = safe_float(row.get("pct_change"))
    code = str(row.get("code") or "")
    if code.startswith(("300", "301", "688")):
        return pct <= -19
    return pct <= -9.7


def _score(value: float, low: float, high: float) -> float:
    if high == low:
        return 50
    return max(0, min(100, (safe_float(value) - low) / (high - low) * 100))


def _inverse_score(value: float, low: float, high: float) -> float:
    return 100 - _score(value, low, high)


def _average(values: list[float]) -> float:
    clean = [safe_float(value) for value in values]
    return sum(clean) / len(clean) if clean else 0
