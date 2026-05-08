from __future__ import annotations

import json
from typing import Any

import pandas as pd

from app.services.analytics import component_scores, safe_float


def parse_parameters(raw: str | dict | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


GENERIC_EXIT_RULES = [
    "策略核心条件失效，退出观察",
    "风险等级升高至高风险，降级为暂不参与",
    "人工复盘确认数据异常，移出观察清单",
]


def evaluate_strategy_row(
    strategy: dict,
    row: pd.Series,
    market_volatility: float = 0.03,
    relaxed: bool = False,
    market_context: dict[str, Any] | None = None,
) -> dict | None:
    params = parse_parameters(strategy.get("parameters"))
    name = strategy.get("name", "")
    market_context = market_context or {}
    market_regime = str(market_context.get("marketRegime") or "Choppy")
    min_score = float(params.get("min_score", 60))
    scores = component_scores(row)
    passed_count = 0
    condition_count = 0
    missed_reasons: list[str] = []
    candidate_types = ["趋势增强"]

    if "均线趋势" in name:
        conditions = _moving_average_conditions(row, market_context)
        candidate_types = ["中期趋势"]
        passed_count = sum(1 for passed, _ in conditions if passed)
        condition_count = len(conditions)
        signal_score = _moving_average_signal_score(row, passed_count, condition_count)
        passed = all(passed for passed, _ in conditions)
        reasons = [text for passed, text in conditions if passed]
        missed_reasons = [text for passed, text in conditions if not passed]
    elif "低回撤趋势" in name:
        max_dd_threshold = float(params.get("max_drawdown_threshold", 0.16))
        vol_threshold = float(params.get("volatility_threshold", market_volatility))
        conditions = [
            (safe_float(row.get("ret60")) > 0, "近60日收益为正"),
            (safe_float(row.get("max_drawdown_60")) < max_dd_threshold, f"近60日回撤低于 {max_dd_threshold:.0%}"),
            (safe_float(row.get("volatility_60")) < max(vol_threshold, market_volatility * 1.08), "波动率低于市场均值附近"),
            (safe_float(row.get("ma20")) > safe_float(row.get("ma60")), "中期趋势向上"),
        ]
        passed_count = sum(1 for passed, _ in conditions if passed)
        condition_count = len(conditions)
        signal_score = 46 + passed_count * 12 + min(max((0.18 - safe_float(row.get("max_drawdown_60"))) * 100, -8), 10)
        passed = all(passed for passed, _ in conditions)
        reasons = [text for passed, text in conditions if passed]
        missed_reasons = [text for passed, text in conditions if not passed]
        candidate_types = ["中期趋势", "低波防御"]
    else:
        weights = params.get("weights", {})
        signal_score = (
            scores["momentum"] * float(weights.get("momentum", 0.25))
            + scores["volatility"] * float(weights.get("volatility", 0.2))
            + scores["volume"] * float(weights.get("volume", 0.15))
            + scores["drawdown"] * float(weights.get("drawdown", 0.2))
            + scores["trend"] * float(weights.get("trend", 0.2))
        )
        passed = signal_score >= min_score
        reasons = _factor_reasons(scores)

    signal_score = max(0, min(100, round(signal_score, 2)))
    risk_pack = evaluate_risk_pack(row, signal_score, market_context, missed_reasons if "均线趋势" in name else [])
    final_score = max(0, min(100, round(signal_score - risk_pack["riskPenalty"], 2)))
    strict_passed = passed and final_score >= min_score and not risk_pack["hardRisk"]
    observation_passed = _observation_passed(name, params, signal_score, min_score, passed_count, condition_count)
    if not strict_passed and (not relaxed or not observation_passed):
        return None

    candidate_mode = _candidate_mode(strict_passed, bool(risk_pack["hardRisk"]), bool(risk_pack["softRisk"]), bool(missed_reasons))
    if not strict_passed:
        if not reasons:
            reasons = ["策略相关性进入观察范围"]
        if "多因子" in name:
            reasons.insert(0, "多因子相关性进入观察范围")
        if missed_reasons:
            reasons.append(f"未满足{_strategy_label(name)}硬条件：{_join_short(missed_reasons)}")
        else:
            reasons.append("未完全满足策略硬条件，按相关性进入观察池")

    risk_level = str(risk_pack["riskLevel"])
    risk_reasons = list(risk_pack["riskReasons"])
    if not strict_passed:
        if missed_reasons:
            risk_reasons.insert(0, f"未满足{_strategy_label(name)}硬条件：{_join_short(missed_reasons)}，因此仅进入{_pool_label(candidate_mode)}")
        else:
            risk_reasons.append("观察候选未完全满足硬条件，需人工确认")
        if risk_level == "low":
            risk_level = "medium"
    suggested_action = _suggested_action(final_score, risk_level, strict_passed, bool(risk_pack["hardRisk"]), market_regime)
    final_score = _cap_final_score(final_score, risk_level, suggested_action, strict_passed)
    strategy_confidence = _strategy_confidence(signal_score, risk_pack["riskPenalty"], strict_passed, market_regime)
    if candidate_mode == "risk_observation":
        candidate_types.append("风险观察")
    if candidate_mode == "review_pool":
        candidate_types.append("复盘观察")
    return {
        "signal_type": "candidate",
        "score": final_score,
        "reason": "；".join(reasons),
        "risk_reason": "；".join(risk_reasons),
        "risk_level": risk_level,
        "component_scores": scores,
        "metadata": {
            "candidateMode": candidate_mode,
            "strictPassed": strict_passed,
            "matchedConditionCount": passed_count,
            "conditionCount": condition_count,
            "candidateLevel": _candidate_level(final_score, strict_passed),
            "suggestedAction": suggested_action,
            "signalScore": signal_score,
            "riskPenalty": round(float(risk_pack["riskPenalty"]), 2),
            "finalScore": final_score,
            "strategyConfidence": strategy_confidence,
            "marketRegime": market_regime,
            "hardRisk": risk_pack["hardRisk"],
            "softRisk": risk_pack["softRisk"],
            "matchedConditions": reasons,
            "missedConditions": missed_reasons,
            "candidateTypes": candidate_types,
            "triggerReasons": reasons,
            "riskReasons": risk_reasons,
            "exitRules": GENERIC_EXIT_RULES,
        },
    }


def evaluate_risk(row: pd.Series, score: float) -> tuple[str, list[str]]:
    pack = evaluate_risk_pack(row, score)
    return str(pack["riskLevel"]), list(pack["riskReasons"])


def evaluate_risk_pack(
    row: pd.Series,
    score: float,
    market_context: dict[str, Any] | None = None,
    missed_conditions: list[str] | None = None,
) -> dict[str, Any]:
    market_context = market_context or {}
    missed_conditions = missed_conditions or []
    reasons: list[str] = []
    hard_risk: list[str] = []
    soft_risk: list[str] = []
    risk_penalty = 0.0
    max_drawdown = safe_float(row.get("max_drawdown_60"))
    volatility = safe_float(row.get("volatility_60"))
    pct_change = safe_float(row.get("pct_change"))
    ret20 = safe_float(row.get("ret20"))
    ret60 = safe_float(row.get("ret60"))
    close = safe_float(row.get("close"))
    ma20 = safe_float(row.get("ma20"))
    ma60 = safe_float(row.get("ma60"))
    ma60_slope = safe_float(row.get("ma60_slope"), safe_float(row.get("trend_slope")))
    amount = safe_float(row.get("amount"))
    index_return20d = safe_float(market_context.get("indexReturn20d")) / 100
    market_regime = str(market_context.get("marketRegime") or "Choppy")
    missing_required = [item for item in ["close", "ma20", "ma60", "ret20", "ret60", "volatility_60", "max_drawdown_60"] if row.get(item) is None or pd.isna(row.get(item))]

    if bool(row.get("is_st")):
        hard_risk.append("ST / *ST 风险警示股票")
    if bool(row.get("is_suspended")):
        hard_risk.append("停牌股票")
    if safe_float(row.get("listed_days"), 120) < 60:
        hard_risk.append("上市不足 60 个交易日")
    if amount and amount < 100000000:
        hard_risk.append("成交额低于 1 亿，流动性不足")
    if max_drawdown > 0.35:
        hard_risk.append(f"60 日最大回撤 {max_drawdown:.1%} 超过 35% 硬风险阈值")
    elif max_drawdown > 0.25:
        soft_risk.append(f"60 日最大回撤 {max_drawdown:.1%} 位于 25%-35% 风险区间")
    if volatility > 0.45:
        hard_risk.append(f"60 日波动率 {volatility:.1%} 超过 45% 硬风险阈值")
    elif volatility > 0.35:
        soft_risk.append(f"60 日波动率 {volatility:.1%} 位于 35%-45% 风险区间")
    if close and ma60 and close < ma60 and ma60_slope < 0:
        hard_risk.append("价格低于 MA60 且 MA60 斜率向下，中期趋势未修复")
    if ret60 < -0.25 and close and ma20 and close < ma20:
        hard_risk.append(f"近 60 日跌幅 {ret60:.1%} 较大且尚未站回 MA20")
    if len(missing_required) >= 3:
        hard_risk.append(f"数据缺失严重：{', '.join(missing_required[:4])}")
    if index_return20d and ret20 <= index_return20d:
        soft_risk.append(f"20 日收益 {ret20:.1%} 弱于市场 {index_return20d:.1%}")
    if amount and amount < 200000000:
        soft_risk.append("成交额低于 2 亿，量能不足")
    if market_regime == "RiskOff":
        soft_risk.append("市场状态为 RiskOff，趋势策略降权")
    if market_regime == "Panic":
        hard_risk.append("市场状态为 Panic，仅保留观察和复盘记录")

    if score < 68:
        soft_risk.append("信号分接近候选阈值")
    elif max_drawdown > 0.12 and max_drawdown <= 0.25:
        reasons.append(f"近60日回撤偏高 {max_drawdown:.1%}")
    if 0.28 < volatility <= 0.35:
        reasons.append(f"波动率需观察 {volatility:.1%}")
    if pct_change > 6:
        soft_risk.append("当日涨幅偏大，追高风险")
    if ret20 > 0.25:
        soft_risk.append("短期涨幅较大，注意回撤")

    if hard_risk:
        risk_penalty += 45 + max(0, len(hard_risk) - 1) * 10
    risk_penalty += len(soft_risk) * 10
    if missed_conditions:
        risk_penalty += min(25, len(missed_conditions) * 4)
    risk_penalty = min(100, risk_penalty)

    reasons = hard_risk + soft_risk + reasons
    if not reasons:
        reasons.append("未触发主要风控阈值")

    if hard_risk:
        level = "high"
    elif soft_risk:
        level = "medium"
    else:
        level = "low"
    return {
        "riskLevel": level,
        "riskReasons": reasons,
        "riskPenalty": round(risk_penalty, 2),
        "hardRisk": hard_risk,
        "softRisk": soft_risk,
    }


def _observation_passed(
    name: str,
    params: dict[str, Any],
    score: float,
    min_score: float,
    passed_count: int,
    condition_count: int,
) -> bool:
    if "多因子" in name:
        threshold = float(params.get("observation_min_score", max(30, min_score * 0.5)))
        return score >= threshold
    threshold = float(params.get("observation_min_score", max(45, min_score * 0.75)))
    min_conditions = int(params.get("observation_min_conditions", max(1, condition_count // 2)))
    return score >= threshold and passed_count >= min_conditions


def _moving_average_conditions(row: pd.Series, market_context: dict[str, Any]) -> list[tuple[bool, str]]:
    close = safe_float(row.get("close"))
    ma20 = safe_float(row.get("ma20"))
    ma60 = safe_float(row.get("ma60"))
    ma20_slope = safe_float(row.get("ma20_slope"), safe_float(row.get("trend_slope")))
    ma60_slope = safe_float(row.get("ma60_slope"), 0)
    ret20 = safe_float(row.get("ret20"))
    ret60 = safe_float(row.get("ret60"))
    max_drawdown = safe_float(row.get("max_drawdown_60"))
    volatility = safe_float(row.get("volatility_60"))
    amount = safe_float(row.get("amount"))
    index_return20d = safe_float(market_context.get("indexReturn20d")) / 100
    return [
        (close > ma20, f"close 高于 MA20（{close:.2f} > {ma20:.2f}）"),
        (ma20 > ma60, f"MA20 高于 MA60（{ma20:.2f} > {ma60:.2f}）"),
        (ma20_slope > 0, f"MA20 斜率为正（{ma20_slope:.2%}）"),
        (ma60_slope >= 0, f"MA60 斜率非负（{ma60_slope:.2%}）"),
        (ret20 > 0, f"20 日收益为正（{ret20:.1%}）"),
        (ret60 > 0, f"60 日收益为正（{ret60:.1%}）"),
        (max_drawdown <= 0.25, f"60 日最大回撤不超过 25%（当前 {max_drawdown:.1%}）"),
        (volatility <= 0.35, f"60 日波动率不超过 35%（当前 {volatility:.1%}）"),
        (amount >= 100000000, f"成交额不低于 1 亿（当前 {amount / 100000000:.1f} 亿）"),
        (not index_return20d or ret20 > index_return20d, f"20 日收益强于市场（个股 {ret20:.1%} / 市场 {index_return20d:.1%}）"),
    ]


def _moving_average_signal_score(row: pd.Series, passed_count: int, condition_count: int) -> float:
    ret20 = safe_float(row.get("ret20"))
    ret60 = safe_float(row.get("ret60"))
    amount_ratio = safe_float(row.get("amount")) / max(safe_float(row.get("amount_ma20"), safe_float(row.get("amount"), 1)), 1)
    base = passed_count / max(condition_count, 1) * 82
    momentum_bonus = min(10, max(0, ret20 * 55 + ret60 * 25))
    liquidity_bonus = min(8, max(0, (amount_ratio - 0.8) * 8))
    return base + momentum_bonus + liquidity_bonus


def _factor_reasons(scores: dict[str, float]) -> list[str]:
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    labels = {
        "momentum": "动量",
        "volatility": "波动率控制",
        "volume": "资金活跃",
        "drawdown": "回撤控制",
        "trend": "趋势",
    }
    return [f"{labels.get(key, key)} {value:.0f}" for key, value in ranked[:4]]


def _candidate_level(score: float, strict_passed: bool) -> str:
    if not strict_passed:
        return "观察候选"
    if score >= 85:
        return "核心候选"
    if score >= 72:
        return "强势候选"
    return "观察候选"


def _suggested_action(score: float, risk_level: str, strict_passed: bool, hard_risk: bool = False, market_regime: str = "Choppy") -> str:
    if risk_level == "high" or hard_risk or market_regime == "Panic":
        return "暂不参与"
    if strict_passed and score >= 80:
        return "谨慎观察"
    return "观察"


def _candidate_mode(strict_passed: bool, hard_risk: bool, soft_risk: bool, missed_conditions: bool) -> str:
    if strict_passed and not hard_risk and not soft_risk:
        return "main_observation"
    if hard_risk or soft_risk:
        return "risk_observation"
    if missed_conditions:
        return "review_pool"
    return "ranked_observation"


def _cap_final_score(score: float, risk_level: str, suggested_action: str, strict_passed: bool) -> float:
    capped = score
    if not strict_passed:
        capped = min(capped, 59)
    if risk_level == "high":
        capped = min(capped, 69)
    if suggested_action == "暂不参与":
        capped = min(capped, 59)
    return round(max(0, min(100, capped)), 2)


def _strategy_confidence(signal_score: float, risk_penalty: float, strict_passed: bool, market_regime: str) -> float:
    confidence = signal_score - risk_penalty * 0.55
    if not strict_passed:
        confidence -= 15
    if market_regime == "RiskOff":
        confidence -= 8
    if market_regime == "Panic":
        confidence -= 30
    return round(max(0, min(100, confidence)), 2)


def _pool_label(candidate_mode: str) -> str:
    return {
        "main_observation": "主观察清单",
        "risk_observation": "风险观察池",
        "review_pool": "复盘池",
        "ranked_observation": "复盘池",
    }.get(candidate_mode, "观察池")


def _join_short(items: list[str], limit: int = 4) -> str:
    suffix = "等" if len(items) > limit else ""
    return "、".join(items[:limit]) + suffix


def _strategy_label(name: str) -> str:
    return name.replace("策略", "")
