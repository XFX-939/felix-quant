from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.services.classic_quant import research_integrity_check

MARKET_REGIME_VALUES = {"RiskOn", "Choppy", "RiskOff", "Panic", "Recovery"}


def split_candidate_layers(signals: list[dict], market_regime: str, market_theme: dict | None = None) -> dict[str, list[dict]]:
    sorted_signals = sorted(signals, key=_candidate_priority, reverse=True)
    risk_pool = [signal for signal in sorted_signals if _is_risk_pool(signal)]
    risk_keys = {_signal_key(signal) for signal in risk_pool}
    defensive = [
        signal
        for signal in sorted_signals
        if _signal_key(signal) not in risk_keys and _is_defensive_watchlist(signal, market_regime)
    ]
    defensive_keys = {_signal_key(signal) for signal in defensive}
    hotspot = [
        signal
        for signal in sorted_signals
        if _signal_key(signal) not in risk_keys
        and _signal_key(signal) not in defensive_keys
        and _is_hotspot_watchlist(signal, market_regime, market_theme)
    ]
    occupied = risk_keys | defensive_keys | {_signal_key(signal) for signal in hotspot}
    main_candidates = [
        signal
        for signal in sorted_signals
        if _signal_key(signal) not in occupied and _is_main_watchlist(signal, market_regime)
    ]
    main = apply_diversity_constraints(main_candidates, market_regime)
    main_keys = {_signal_key(signal) for signal in main}
    occupied |= main_keys
    review = [
        signal
        for signal in sorted_signals
        if _signal_key(signal) not in occupied
        and not _is_risk_pool(signal)
        and (_candidate_mode(signal) in {"review_pool", "ranked_observation", "risk_observation"} or _score(signal) < 60)
    ][:20]
    return {
        "mainWatchlist": main,
        "defensiveWatchlist": defensive[:20],
        "hotspotWatchlist": hotspot[:20],
        "riskPool": risk_pool[:30],
        "reviewPool": review,
    }


def build_daily_decision(
    trade_date: str | None,
    market_regime: str,
    layers: dict[str, list[dict]],
    strategy_health: list[dict],
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    regime = market_regime if market_regime in MARKET_REGIME_VALUES else "Choppy"
    market_context = market_context or {}
    recovery_override = bool(
        market_context.get("intradayRecoveryOverride")
        or market_context.get("strongRecoverySignal")
        or market_context.get("superRiskOnSignal")
    )
    main_count = len(layers.get("mainWatchlist", []))
    hotspot_count = len(layers.get("hotspotWatchlist", []))
    defensive_count = len(layers.get("defensiveWatchlist", []))
    actionable_count = main_count + defensive_count + hotspot_count
    all_candidates = _all_layer_candidates(layers)
    high_risk_ratio = _ratio(sum(1 for item in all_candidates if item.get("risk_level") == "high"), len(all_candidates))
    average_score = sum(_score(item) for item in all_candidates) / max(len(all_candidates), 1)
    key_reasons: list[str] = []

    if regime == "Panic":
        mode = "WAIT"
        position = (0.0, 0.0)
        allowed = ["复盘风险候选", "检查数据质量"]
        forbidden = ["短线追涨", "龙头接力", "趋势突破", "加仓"]
        key_reasons.append("市场状态为 Panic，仅保留观察和复盘记录")
    elif regime == "RiskOff":
        mode = "DEFENSIVE_OBSERVE"
        position = (0.0, 0.2)
        allowed = ["观察低波防御", "观察质量动量", "复盘风险候选"]
        forbidden = ["短线热点追涨", "龙头接力", "扩大仓位"]
        if main_count == 0:
            key_reasons.append("主观察清单为空，今日不适合新增进攻观察")
        if defensive_count > 0:
            key_reasons.append(f"存在 {defensive_count} 只防御观察候选，可用于低风险跟踪")
    elif regime == "Choppy":
        mode = "WATCH"
        position = (0.0, 0.3)
        allowed = ["谨慎观察", "观察质量动量", "观察低回撤趋势", "复盘短线候选"]
        forbidden = ["扩大仓位", "追涨高风险热点"]
        key_reasons.append("市场处于震荡状态，优先质量动量、低回撤趋势和低波策略")
    elif regime == "Recovery":
        mode = "WATCH"
        position = (0.1, 0.3)
        allowed = ["观察主线强势股", "观察趋势突破", "复盘热点持续性"]
        forbidden = ["追高炸板票", "扩大到重仓", "无主线单票追涨"]
        key_reasons.append("市场出现强修复，但仍需确认持续性。")
    elif regime == "RiskOn" and (recovery_override or (actionable_count >= 3 and high_risk_ratio < 0.3)):
        mode = "PROBE"
        position = (0.2, 0.5)
        allowed = ["观察主线龙头", "观察趋势突破", "观察放量强势股"]
        forbidden = ["追高高位放量滞涨票", "无风控扩大仓位"]
        key_reasons.append("市场成交放量且上涨家数显著增加，风险偏好恢复。")
    else:
        mode = "WATCH"
        position = (0.0, 0.25)
        allowed = ["谨慎观察", "复盘候选"]
        forbidden = ["扩大仓位", "短线追涨"]

    if regime == "RiskOn" and main_count == 0 and hotspot_count == 0:
        mode = "WATCH"
        position = (0.0, min(position[1], 0.3))
        key_reasons.append("市场状态偏强，但当前无明确可观察标的，先观察主线持续性。")
    if mode == "PROBE" and (
        regime not in {"RiskOn", "Recovery"}
        or actionable_count < 2
        or main_count + hotspot_count < 2
        or high_risk_ratio >= 0.6
    ):
        mode = "WATCH"
        position = (0.0, min(position[1], 0.3))
        key_reasons.append("小仓试探条件不足，需至少 2 只可展示观察候选且高风险比例低于 60%。")

    probe_floor_allowed = (
        bool(market_context.get("superRiskOnSignal"))
        and regime == "RiskOn"
        and actionable_count >= 2
        and main_count + hotspot_count >= 2
        and high_risk_ratio < 0.6
    )
    downgrade_floor = "PROBE" if probe_floor_allowed else "WATCH" if recovery_override and regime in {"Recovery", "RiskOn"} else None
    if average_score < 50:
        mode = _downgrade_mode(mode, floor=downgrade_floor)
        key_reasons.append("多策略平均分低于可行动阈值，今日以观察和复盘为主")
    if high_risk_ratio > 0.5:
        mode = _downgrade_mode(mode, floor=downgrade_floor)
        key_reasons.append("高风险候选比例过高，策略信号质量不足")
    if any(item.get("status") in {"暂停", "仅复盘"} for item in strategy_health):
        key_reasons.append("部分策略今日暂停或仅复盘，需降低策略信号权重")
    if main_count == 0 and actionable_count > 0 and regime in {"RiskOn", "Recovery"}:
        key_reasons.append(f"主观察清单仍需等待硬条件确认，但已有 {actionable_count} 只降级观察候选可用于人工跟踪")
    elif main_count == 0 and "主观察清单为空，今日不适合新增进攻观察" not in key_reasons:
        key_reasons.append("主观察清单为空，今日以等待、风险跟踪和复盘为主")

    position, allowed, forbidden = _normalize_decision_controls(mode, position, allowed, forbidden)
    position_decision = build_position_decision(regime, layers, strategy_health, mode, market_context=market_context)
    position = (position_decision["finalPositionMin"], position_decision["finalPositionMax"])
    guidance = _decision_guidance(mode, regime, layers, strategy_health, high_risk_ratio, average_score, market_context)
    text = _decision_text(mode, regime, position, key_reasons)
    return {
        "tradeDate": trade_date,
        "decisionMode": mode,
        "decisionText": text,
        "marketRegime": regime,
        "suggestedTotalPositionMin": position[0],
        "suggestedTotalPositionMax": position[1],
        "allowedActions": allowed,
        "forbiddenActions": forbidden,
        "keyReasons": key_reasons[:5],
        "nextCheck": "下一交易日收盘后重新更新数据并运行策略",
        "positionDecision": position_decision,
        "whyCurrentMode": guidance["whyCurrentMode"],
        "waitingSignals": guidance["waitingSignals"],
        "switchConditions": guidance["switchConditions"],
    }


def build_position_decision(
    market_regime: str,
    layers: dict[str, list[dict]],
    strategy_health: list[dict],
    decision_mode: str,
    base_risk_limit: float = 0.65,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    regime = market_regime if market_regime in MARKET_REGIME_VALUES else "Choppy"
    market_context = market_context or {}
    recovery_override = bool(
        market_context.get("intradayRecoveryOverride")
        or market_context.get("strongRecoverySignal")
        or market_context.get("superRiskOnSignal")
    )
    super_risk_on = bool(market_context.get("superRiskOnSignal"))
    all_candidates = _all_layer_candidates(layers)
    main_count = len(layers.get("mainWatchlist", []))
    hotspot_count = len(layers.get("hotspotWatchlist", []))
    high_risk_ratio = _ratio(sum(1 for item in all_candidates if item.get("risk_level") == "high"), len(all_candidates))
    average_score = sum(_score(item) for item in all_candidates) / max(len(all_candidates), 1)
    effective_count = sum(1 for item in strategy_health if item.get("status") == "有效")
    market_limit = {
        "RiskOn": 0.70,
        "Recovery": 0.50,
        "Choppy": 0.30,
        "RiskOff": 0.20,
        "Panic": 0.0,
    }.get(regime, 0.30)
    strategy_quality_limit = base_risk_limit
    quality_reasons: list[str] = []
    if effective_count >= 3 and main_count >= 5:
        quality_reasons.append("有效策略不少于 3 个且主观察清单不少于 5 只，策略质量不额外降权")
    if main_count == 0 and not (recovery_override and regime in {"Recovery", "RiskOn"}):
        strategy_quality_limit = min(strategy_quality_limit, 0.0)
        quality_reasons.append("主观察清单为 0，策略质量上限降至 0%")
    if high_risk_ratio > 0.5 and not super_risk_on:
        strategy_quality_limit = min(strategy_quality_limit, 0.20)
        quality_reasons.append("高风险候选比例超过 50%，策略质量上限不超过 20%")
    if average_score < 50 and not (recovery_override and regime in {"Recovery", "RiskOn"}):
        strategy_quality_limit = min(strategy_quality_limit, 0.20)
        quality_reasons.append("多策略平均分低于 50，策略质量上限不超过 20%")
    if recovery_override and regime in {"Recovery", "RiskOn"}:
        quality_reasons.append("当日强修复覆盖已触发，仓位上限不因本地样本候选为空直接归零")

    decision_mode_limits = {
        "WAIT": (0.0, 0.0),
        "DEFENSIVE_OBSERVE": (0.0, 0.20),
        "WATCH": (0.0, 0.30),
        "PROBE": (0.20, 0.50),
        "RISK_OFF": (0.0, 0.0),
    }
    decision_min, decision_max = decision_mode_limits.get(decision_mode, (0.0, 0.30))
    if recovery_override and regime == "Recovery" and decision_mode == "WATCH":
        decision_min = 0.10
    final_max = min(base_risk_limit, market_limit, strategy_quality_limit, decision_max)
    final_min = min(decision_min, final_max)
    return {
        "baseRiskLimit": round(base_risk_limit, 4),
        "marketRegimeLimit": round(market_limit, 4),
        "strategyQualityLimit": round(strategy_quality_limit, 4),
        "decisionModeLimitMin": round(decision_min, 4),
        "decisionModeLimitMax": round(decision_max, 4),
        "finalPositionMin": round(final_min, 4),
        "finalPositionMax": round(final_max, 4),
        "mainWatchlistCount": main_count,
        "hotspotWatchlistCount": hotspot_count,
        "effectiveStrategyCount": effective_count,
        "highRiskRatio": round(high_risk_ratio, 4),
        "averageScore": round(average_score, 2),
        "reasons": quality_reasons or ["仓位由基础风控、市场状态、策略质量和决策模式共同修正"],
        "explanation": "基础仓位上限不是今日建议仓位，今日最终仓位由 DecisionEngine 修正。",
    }


def evaluate_strategy_health(
    signals: list[dict],
    strategies: list[dict],
    market_regime: str,
    critical_hotspot_data_missing: bool = False,
    latest_backtests: dict[str, dict] | None = None,
) -> list[dict]:
    latest_backtests = latest_backtests or {}
    by_strategy: dict[str, list[dict]] = defaultdict(list)
    for signal in signals:
        by_strategy[str(signal.get("strategy_name") or "未知策略")].append(signal)
    names = [str(strategy.get("name")) for strategy in strategies] if strategies else sorted(by_strategy)
    health: list[dict] = []
    for name in names:
        items = by_strategy.get(name, [])
        candidate_count = len(items)
        main_count = sum(1 for item in items if _is_main_watchlist(item, market_regime))
        high_count = sum(1 for item in items if item.get("risk_level") == "high")
        average_score = sum(_score(item) for item in items) / max(candidate_count, 1)
        high_ratio = _ratio(high_count, candidate_count)
        enabled = next((bool(strategy.get("enabled", True)) for strategy in strategies if strategy.get("name") == name), True)
        backtest = latest_backtests.get(name)
        status, reason = _strategy_health_status(
            name,
            candidate_count,
            main_count,
            average_score,
            high_ratio,
            market_regime,
            enabled,
            critical_hotspot_data_missing,
            backtest,
        )
        health.append(
            {
                "strategyName": name,
                "candidateCount": candidate_count,
                "mainCount": main_count,
                "highRiskCount": high_count,
                "averageScore": round(average_score, 2),
                "highRiskRatio": round(high_ratio, 4),
                "enabled": enabled,
                "status": status,
                "reason": reason,
                "backtestValidity": (backtest or {}).get("validity"),
                "latestBacktestTradeCount": (backtest or {}).get("trade_count"),
            }
        )
    return sorted(health, key=lambda item: (item["status"] != "有效", -item["candidateCount"], item["strategyName"]))


def evaluate_candidate_diversity(signals: list[dict]) -> dict[str, Any]:
    today_codes = [str(signal.get("stock_code")) for signal in signals]
    unique_codes = sorted(set(today_codes))
    industry_counter = Counter(str(signal.get("industry") or "未分类") for signal in signals)
    strategy_counter = Counter(str(signal.get("strategy_name") or "未知策略") for signal in signals)
    large_cap_candidates = [signal for signal in signals if _is_large_cap_bluechip(signal)]
    top_repeated = [{"code": code, "name": _name_for_code(signals, code), "appearances": count} for code, count in Counter(today_codes).most_common(5)]
    max_industry_ratio = max(industry_counter.values(), default=0) / max(len(signals), 1)
    strategy_concentration = max(strategy_counter.values(), default=0) / max(len(signals), 1)
    large_cap_ratio = len(large_cap_candidates) / max(len(signals), 1)
    repeat_rate = 1 - len(unique_codes) / max(len(signals), 1)
    warnings = []
    if repeat_rate > 0.7:
        warnings.append("候选池新鲜度不足，可能过度依赖蓝筹和流动性因子。")
    if large_cap_ratio > 0.5:
        warnings.append("候选池偏蓝筹，建议提高热点题材和中小市值强势因子权重。")
    if max_industry_ratio > 0.3:
        warnings.append("单行业占比超过 30%，存在行业集中风险。")
    return {
        "repeatRate1d": round(repeat_rate, 4),
        "repeatRate5d": round(repeat_rate, 4),
        "newCandidateCount": len(unique_codes),
        "droppedCandidateCount": 0,
        "topRepeatedCandidates": top_repeated,
        "industryConcentration": round(max_industry_ratio, 4),
        "strategyConcentration": round(strategy_concentration, 4),
        "largeCapRatio": round(large_cap_ratio, 4),
        "warnings": warnings,
    }


def evaluate_missed_opportunity_risk(
    market_regime: str,
    layers: dict[str, list[dict]],
    market_theme: dict | None,
    funnel: dict | None,
) -> dict[str, Any]:
    main_count = len(layers.get("mainWatchlist", []))
    hotspot_count = len(layers.get("hotspotWatchlist", []))
    initial_count = int((funnel or {}).get("strategyInitialCandidates") or 0)
    actionable_count = int((funnel or {}).get("finalActionableCandidates") or main_count + hotspot_count + len(layers.get("defensiveWatchlist", [])))
    confidence = (market_theme or {}).get("confidence")
    reasons: list[str] = []
    fixes: list[str] = []
    level_rank = 0
    if market_regime == "RiskOn" and main_count == 0:
        level_rank = max(level_rank, 3)
        reasons.append("RiskOn 状态下主观察清单为空，可能错过主线行情。")
        fixes.append("放宽 RiskOn 下回撤和波动动态阈值，并优先检查热点观察清单。")
    if confidence in {"中", "高"} and hotspot_count == 0:
        level_rank = max(level_rank, 3)
        reasons.append("今日主线已识别，但热点观察清单为空，主线到个股映射失败。")
        fixes.append("补充行业/概念映射，将科技成长、半导体、算力、CPO、PCB 等方向纳入降级匹配。")
    if initial_count >= 50 and actionable_count <= 2:
        level_rank = max(level_rank, 2 if actionable_count > 0 else 3)
        reasons.append("策略筛选漏斗过窄，可能存在风控阈值过严。")
        fixes.append("拆解基础过滤、风控剔除、非主线剔除和数据缺失剔除比例。")
    if not reasons:
        reasons.append("主线识别、候选生成和风险过滤之间暂无明显踏空风险。")
        fixes.append("继续观察主线延续性和候选质量变化。")
    return {
        "level": "高" if level_rank >= 3 else "中" if level_rank == 2 else "低",
        "reasons": reasons,
        "suggestedFixes": fixes,
    }


def detect_market_themes(market_context: dict, signals: list[dict], coverage: dict | None = None) -> dict[str, Any]:
    sector_stats = market_context.get("sectorStats") or {}
    coverage = coverage or data_coverage_panel(market_context)
    critical_missing = _critical_hotspot_data_missing(coverage)
    themes = []
    snapshot_data = ((market_context.get("marketSnapshot") or {}).get("data") or {})
    if isinstance(snapshot_data, dict):
        for snapshot_theme in snapshot_data.get("themes") or []:
            if not isinstance(snapshot_theme, dict):
                continue
            name = str(snapshot_theme.get("name") or "市场线索")
            themes.append(
                {
                    "name": name,
                    "level": str(snapshot_theme.get("level") or "行业降级"),
                    "themeScore": round(float(snapshot_theme.get("themeScore") or 0), 2),
                    "confidence": str(snapshot_theme.get("confidence") or "中"),
                    "relatedSectors": [str(item) for item in (snapshot_theme.get("relatedSectors") or [name])],
                    "evidence": [str(item) for item in (snapshot_theme.get("evidence") or [])],
                    "dataBasis": [str(item) for item in (snapshot_theme.get("dataBasis") or _theme_data_basis(coverage))],
                    "missingData": [str(item) for item in (snapshot_theme.get("missingData") or _theme_missing_data(coverage))],
                    "sectorPctChg": round(float(snapshot_theme.get("sectorPctChg") or 0), 2),
                    "sectorRank": int(snapshot_theme.get("sectorRank") or 99),
                    "sectorLimitUpCount": int(snapshot_theme.get("sectorLimitUpCount") or 0),
                    "sectorStrongStockCount": int(snapshot_theme.get("sectorStrongStockCount") or 0),
                    "sectorAmountChange": round(float(snapshot_theme.get("sectorAmountChange") or 0), 4),
                    "continuationDays": int(snapshot_theme.get("continuationDays") or 1),
                }
            )
    for sector, stats in sector_stats.items():
        score = _theme_score(stats)
        if score >= 60:
            themes.append(
                {
                    "name": sector,
                    "level": "行业降级" if critical_missing else "完整题材",
                    "themeScore": round(score, 2),
                    "confidence": "中" if critical_missing else "高",
                    "relatedSectors": [sector],
                    "evidence": _sector_theme_evidence(sector, stats, critical_missing),
                    "dataBasis": _theme_data_basis(coverage),
                    "missingData": _theme_missing_data(coverage),
                    "sectorPctChg": round(float(stats.get("sectorPctChg") or 0), 2),
                    "sectorRank": int(stats.get("sectorRank") or 99),
                    "sectorLimitUpCount": int(stats.get("sectorLimitUpCount") or 0),
                    "sectorStrongStockCount": int(stats.get("sectorStrongStockCount") or 0),
                    "sectorAmountChange": round(float(stats.get("sectorAmountChange") or 0), 4),
                    "continuationDays": int(stats.get("continuationDays") or 1),
                }
            )
    themes.extend(_style_theme_estimates(market_context, coverage))
    themes.sort(key=lambda item: item["themeScore"], reverse=True)
    incomplete = critical_missing or not any((stats.get("sectorLimitUpCount") or 0) > 0 for stats in sector_stats.values())
    top_confidence = _theme_confidence(themes, incomplete)
    if themes:
        names = " / ".join(item["name"] for item in themes[:3])
        if incomplete:
            message = "热点判断为降级估算，当前基于行业涨幅、强势股数量和指数风格估算。"
            display = f"主线识别：{names}，可信度{top_confidence}。当前基于行业涨幅、涨停数量和指数风格估算。"
        else:
            message = "基于板块涨幅、涨停扩散、连板高度和成交额变化识别。"
            display = f"今日主线：{names}"
    else:
        message = "题材数据不足，当前仅基于行业涨幅和候选分布估算"
        display = f"行业估算线索：{message}"
    return {
        "themes": themes[:5],
        "isComplete": not incomplete,
        "confidence": top_confidence,
        "message": message,
        "displayText": display,
    }


def data_coverage_panel(market_context: dict | None = None) -> dict[str, Any]:
    items = [
        {"name": "日线行情", "status": "已接入", "reason": "SQLite daily_prices 已可用"},
        {"name": "指数行情", "status": "降级估算", "reason": "当前使用本地股票池近似市场指数"},
        {"name": "行业数据", "status": "降级估算", "reason": "当前使用股票行业字段聚合估算行业强度"},
        {"name": "概念题材数据", "status": "缺失", "reason": "尚未接入概念题材和成分股"},
        {"name": "涨停数据", "status": "缺失", "reason": "尚未接入每日涨停池"},
        {"name": "跌停数据", "status": "缺失", "reason": "尚未接入每日跌停池"},
        {"name": "炸板数据", "status": "缺失", "reason": "尚未接入炸板未回封数据"},
        {"name": "连板数据", "status": "缺失", "reason": "尚未接入连板池和连板高度"},
        {"name": "板块资金数据", "status": "降级估算", "reason": "当前用行业成交额相对变化估算"},
        {"name": "财务数据", "status": "降级估算", "reason": "部分财务因子使用代理值，公告日期处理未完成"},
        {"name": "复权因子", "status": "缺失", "reason": "当前未独立记录复权因子版本"},
        {"name": "停牌/ST/退市数据", "status": "降级估算", "reason": "当前按名称和本地字段近似处理"},
    ]
    missing = [item["name"] for item in items if item["status"] == "缺失"]
    critical_missing = any(name in missing for name in ["概念题材数据", "涨停数据", "炸板数据", "连板数据"])
    warnings = []
    if critical_missing:
        warnings.append("热点和龙头判断缺少关键数据，当前以降级估算参与观察，不输出强判断。")
    return {
        "items": items,
        "criticalHotspotDataMissing": critical_missing,
        "themeConfidence": "低" if critical_missing else "高",
        "warnings": warnings,
    }


def data_quality_panel(market_context: dict | None = None) -> dict[str, Any]:
    coverage = data_coverage_panel(market_context)
    integrity = research_integrity_check(
        {
            "lookaheadBiasChecked": True,
            "stSuspensionDelistHandled": True,
            "runTimestamp": True,
            "reproducibleTradeDate": True,
            "transactionCost": True,
            "slippage": False,
            "parameterVersion": False,
            "dataVersion": False,
            "financialAnnouncementLag": False,
            "survivorshipBiasChecked": False,
        }
    )
    warnings = list(integrity["integrityWarnings"])
    warnings.insert(0, "涨停、炸板、连板和概念题材数据尚未接入，热点策略仅供粗略观察")
    warnings.extend(coverage["warnings"])
    return {
        "priceDataUpdated": True,
        "limitUpDataReady": False,
        "brokenLimitDataReady": False,
        "conceptDataReady": False,
        "financialAnnouncementReady": False,
        "feeIncluded": True,
        "slippageIncluded": False,
        "futureFunctionRisk": "需持续检查",
        "dataVersion": "local-sqlite-sample",
        "strategyParameterVersion": "v1-local",
        "integrityScore": integrity["integrityScore"],
        "integrityLevel": integrity["integrityLevel"],
        "integrityWarnings": warnings,
        "dataCoverage": coverage,
    }


def apply_diversity_constraints(candidates: list[dict], market_regime: str) -> list[dict]:
    selected: list[dict] = []
    industry_count: Counter[str] = Counter()
    strategy_count: Counter[str] = Counter()
    large_cap_count = 0
    max_large_cap = 6
    for signal in candidates:
        if len(selected) >= 20:
            break
        industry = str(signal.get("industry") or "未分类")
        strategy = str(signal.get("strategy_name") or "未知策略")
        if industry_count[industry] >= 3:
            continue
        if strategy_count[strategy] >= _strategy_cap(strategy, market_regime):
            continue
        is_large_cap = _is_large_cap_bluechip(signal)
        if is_large_cap and large_cap_count >= max_large_cap:
            continue
        selected.append(signal)
        industry_count[industry] += 1
        strategy_count[strategy] += 1
        if is_large_cap:
            large_cap_count += 1
    return selected


def _is_main_watchlist(signal: dict, market_regime: str) -> bool:
    return (
        signal.get("suggestedAction") in {"谨慎观察", "观察"}
        and signal.get("risk_level") != "high"
        and _score(signal) >= _min_final_score(market_regime)
        and _candidate_mode(signal) == "main_observation"
        and _strategy_allowed(signal, market_regime)
    )


def _is_defensive_watchlist(signal: dict, market_regime: str) -> bool:
    text = _strategy_text(signal)
    return (
        market_regime in {"RiskOff", "Choppy", "Panic"}
        and any(key in text for key in ["低波防御", "质量动量", "低回撤"])
        and signal.get("risk_level") in {"low", "medium"}
        and signal.get("suggestedAction") == "观察"
        and not _hard_risk(signal)
    )


def _is_hotspot_watchlist(signal: dict, market_regime: str, market_theme: dict | None = None) -> bool:
    text = _strategy_text(signal)
    hotspot_score = float(signal.get("hotspotScore") or signal.get("dragonScore") or signal.get("score") or 0)
    theme_match = _matches_mainline_candidate(signal, market_theme)
    theme_guided = bool(market_theme and market_theme.get("confidence") in {"中", "高"} and (market_theme.get("themes") or []))
    score_qualified = hotspot_score >= (82 if theme_guided else 60)
    return (
        market_regime in {"RiskOn", "Recovery"}
        and any(key in text for key in ["市场热点", "短线龙头", "热点题材", "龙头候选"])
        and (theme_match or (score_qualified and not _is_large_cap_bluechip(signal)))
        and signal.get("risk_level") != "high"
    )


def _is_risk_pool(signal: dict) -> bool:
    return signal.get("risk_level") == "high" or signal.get("suggestedAction") == "暂不参与" or _hard_risk(signal)


def _signal_key(signal: dict) -> str:
    if signal.get("id") is not None:
        return str(signal["id"])
    return f"{signal.get('stock_code')}:{signal.get('strategy_name')}:{signal.get('signal_type')}"


def _strategy_health_status(
    name: str,
    candidate_count: int,
    main_count: int,
    average_score: float,
    high_ratio: float,
    market_regime: str,
    enabled: bool,
    critical_hotspot_data_missing: bool = False,
    latest_backtest: dict | None = None,
) -> tuple[str, str]:
    if not enabled:
        return "暂停", "策略未启用"
    if latest_backtest:
        validity = latest_backtest.get("validity") or {}
        total_return = float(latest_backtest.get("total_return") or 0)
        win_rate = float(latest_backtest.get("win_rate") or 0)
        if not validity.get("usableForStrategyJudgement", False):
            return "仅复盘", f"最近回测{validity.get('validityLevel', '可信度不足')}，交易次数 {latest_backtest.get('trade_count', 0)}，不得参与今日主决策"
        if win_rate < 0.4 and total_return < 0:
            return "仅复盘", f"最近回测收益 {total_return:.1%} 且胜率 {win_rate:.1%}，策略今日仅用于复盘"
        if float(latest_backtest.get("max_drawdown") or 0) > 0.25:
            return "降权", "最近回测最大回撤偏高，策略今日降权"
    if "低波防御" in name and market_regime in {"RiskOn", "Recovery"}:
        return "降权", f"{market_regime} 环境下市场风险偏好修复，低波防御策略今日降权"
    if critical_hotspot_data_missing and "短线龙头" in name:
        if market_regime in {"RiskOn", "Recovery"}:
            return "降权", "涨停、连板和炸板数据不足，短线龙头策略降级观察为短线强势线索"
        return "暂停", "关键涨停、炸板、连板和题材数据缺失，短线龙头策略当前不可用"
    if critical_hotspot_data_missing and "市场热点" in name:
        if market_regime in {"RiskOn", "Recovery"}:
            return "降权", "热点关键数据不足，使用日线涨幅、行业强度和成交额做降级估算"
        return "仅复盘", "热点关键数据不足，仅输出粗略观察和复盘，不参与今日决策"
    if not _strategy_name_allowed(name, market_regime):
        return "暂停", f"{market_regime} 市场状态下该策略暂停或明显降权"
    if candidate_count > 0 and main_count == 0:
        return "仅复盘", "有候选但无主观察标的，今日不作为行动依据"
    if average_score < 50:
        return "降权", "平均分低于 50，策略信号质量不足"
    if high_ratio > 0.5:
        return "暂停", "高风险候选比例超过 50%"
    if high_ratio > 0.3:
        return "降权", "高风险候选比例偏高"
    return "有效", "存在可观察候选且风险比例可控"


def _strategy_allowed(signal: dict, market_regime: str) -> bool:
    return _strategy_name_allowed(str(signal.get("strategy_name") or ""), market_regime)


def _strategy_name_allowed(name: str, market_regime: str) -> bool:
    if market_regime == "Panic":
        return any(key in name for key in ["低波防御", "质量动量"])
    if market_regime == "RiskOff":
        return not any(key in name for key in ["市场热点", "短线龙头", "均线趋势", "趋势跟踪"])
    if market_regime == "Choppy":
        return not any(key in name for key in ["短线龙头"])
    return True


def _candidate_priority(signal: dict) -> float:
    return (
        _action_rank(signal.get("suggestedAction")) * 10000
        + _risk_rank(signal.get("risk_level")) * 1000
        + _candidate_level_rank(signal.get("candidateLevel")) * 350
        + float(signal.get("strategyConfidence") or signal.get("score") or 0) * 4
        + _score(signal) * 3
        + min(float(signal.get("amount") or 0) / 100000000, 50)
    )


def _theme_score(stats: dict) -> float:
    sector_rank = int(stats.get("sectorRank") or 99)
    rank_score = max(0, min(100, (30 - sector_rank + 1) / 30 * 100))
    limit_up_score = max(0, min(100, float(stats.get("sectorLimitUpCount") or 0) / 5 * 100))
    strong_stock_score = max(0, min(100, float(stats.get("sectorStrongStockCount") or 0) / 10 * 100))
    amount_score = max(0, min(100, float(stats.get("sectorAmountChange") or 0) / 0.5 * 100))
    continuation_score = max(0, min(100, float(stats.get("continuationDays") or 1) / 3 * 100))
    return 0.25 * rank_score + 0.25 * limit_up_score + 0.20 * strong_stock_score + 0.20 * amount_score + 0.10 * continuation_score


def _style_theme_estimates(market_context: dict, coverage: dict) -> list[dict[str, Any]]:
    themes: list[dict[str, Any]] = []
    cyb = float(market_context.get("cybIndexPctChg") or 0)
    kc50 = float(market_context.get("kc50PctChg") or 0)
    total_amount_change = float(market_context.get("totalAmountChange") or market_context.get("amountChange20d") or 0)
    up_ratio = float(market_context.get("snapshotUpStockRatio") or market_context.get("upStockRatio") or 0)
    limit_up = int(float(market_context.get("snapshotLimitUpCount") or market_context.get("limitUpCount") or 0))
    if cyb >= 2 or kc50 >= 4 or float(market_context.get("growthStyleStrength") or 0) >= 3:
        score = min(96, 55 + max(cyb, 0) * 5 + max(kc50, 0) * 4 + max(total_amount_change, 0) * 40 + min(limit_up / 100, 1) * 12)
        themes.append(
            {
                "name": "科技成长",
                "level": "风格估算",
                "confidence": "中" if score >= 70 and up_ratio >= 0.6 else "低",
                "themeScore": round(score, 2),
                "relatedSectors": ["半导体", "存储芯片", "算力", "CPO", "PCB"],
                "evidence": [
                    f"创业板指涨幅 {cyb:.2f}%",
                    f"科创50涨幅 {kc50:.2f}%",
                    f"全市场成交额变化 {total_amount_change:.1%}",
                    f"涨停数量约 {limit_up} 只",
                ],
                "dataBasis": _theme_data_basis(coverage),
                "missingData": _theme_missing_data(coverage),
                "sectorPctChg": max(cyb, kc50),
                "sectorRank": 1,
                "sectorLimitUpCount": limit_up,
                "sectorStrongStockCount": int(float(market_context.get("upStockCount") or 0)),
                "sectorAmountChange": total_amount_change,
                "continuationDays": 1,
            }
        )
    return themes


def _sector_theme_evidence(sector: str, stats: dict, degraded: bool) -> list[str]:
    evidence = [
        f"{sector}涨幅排名第 {int(stats.get('sectorRank') or 99)}",
        f"板块平均涨幅 {float(stats.get('sectorPctChg') or 0):.2f}%",
        f"强势股数量 {int(stats.get('sectorStrongStockCount') or 0)} 只",
        f"成交额变化 {float(stats.get('sectorAmountChange') or 0):.1%}",
    ]
    if degraded:
        evidence.append("概念、连板和炸板数据暂缺，当前为行业降级估算")
    else:
        evidence.append(f"涨停扩散 {int(stats.get('sectorLimitUpCount') or 0)} 只")
    return evidence


def _theme_confidence(themes: list[dict], incomplete: bool) -> str:
    if not themes:
        return "低"
    if not incomplete and any(item.get("confidence") == "高" for item in themes):
        return "高"
    if any(item.get("confidence") in {"中", "高"} for item in themes):
        return "中"
    return "低"


def _score(signal: dict) -> float:
    return float(signal.get("finalScore") or signal.get("score") or 0)


def _candidate_mode(signal: dict) -> str:
    return str(signal.get("candidateMode") or (signal.get("metadata") or {}).get("candidateMode") or "")


def _hard_risk(signal: dict) -> bool:
    hard = signal.get("hardRisk") or (signal.get("metadata") or {}).get("hardRisk") or []
    return bool(hard)


def _strategy_text(signal: dict) -> str:
    types = signal.get("candidateTypes") or []
    return f"{signal.get('strategy_name', '')} {' '.join(map(str, types))}"


def _action_rank(action: str | None) -> int:
    return 3 if action == "谨慎观察" else 2 if action == "观察" else 1


def _risk_rank(level: str | None) -> int:
    return 3 if level == "low" else 2 if level == "medium" else 1


def _candidate_level_rank(level: str | None) -> int:
    text = str(level or "")
    if "核心" in text:
        return 3
    if "强势" in text:
        return 2
    return 1


def _strategy_cap(strategy: str, market_regime: str) -> int:
    if "低波防御" in strategy and market_regime == "RiskOff":
        return 5
    if any(key in strategy for key in ["市场热点", "短线热点"]) and market_regime == "RiskOn":
        return 8
    return 5


def _min_final_score(market_regime: str) -> float:
    if market_regime in {"RiskOn", "Recovery"}:
        return 55
    if market_regime == "Choppy":
        return 60
    return 65


def _matches_mainline_candidate(signal: dict, market_theme: dict | None) -> bool:
    if not market_theme or market_theme.get("confidence") not in {"中", "高"}:
        return False
    themes = market_theme.get("themes") or []
    related_terms: set[str] = set()
    for theme in themes:
        name = str(theme.get("name") or "")
        if name == "科技成长":
            related_terms.update(["半导体", "存储芯片", "算力", "CPO", "PCB", "通信设备", "元器件", "云计算", "数据中心", "计算机", "电子", "电力设备", "新能源"])
        if "有色" in name:
            related_terms.add("有色金属")
        related_terms.update(str(item) for item in theme.get("relatedSectors") or [])
    raw = signal.get("rawFactors") or (signal.get("strategyCandidate") or {}).get("rawFactors") or {}
    haystack = " ".join(
        [
            str(signal.get("industry") or ""),
            str(signal.get("stock_name") or ""),
            str(raw.get("sectorName") or raw.get("industryName") or ""),
            " ".join(str(item) for item in raw.get("conceptNames") or []),
        ]
    )
    if related_terms and not any(term and term in haystack for term in related_terms):
        return False
    pct_chg = float(raw.get("pctChg") or signal.get("pct_change") or 0)
    amount_ratio = float(raw.get("amountRatio20d") or 0)
    volume_ratio = float(raw.get("volumeRatio") or signal.get("volumeRatio") or 0)
    ret3 = float(raw.get("return3d") or 0)
    ret5 = float(raw.get("return5d") or 0)
    trend_ok = bool(raw.get("closeAboveMa5") or raw.get("closeAboveMa10"))
    same_day_breakout = pct_chg > 3 and (amount_ratio > 1.5 or volume_ratio > 1.5)
    degraded_momentum = ret5 > 5 and (amount_ratio > 1.5 or volume_ratio > 1.5)
    return (same_day_breakout or degraded_momentum) and (ret3 > 3 or ret5 > 5) and trend_ok


def _is_large_cap_bluechip(signal: dict) -> bool:
    text = f"{signal.get('stock_name', '')}{signal.get('industry', '')}"
    return any(key in text for key in ["招商银行", "贵州茅台", "伊利股份", "平安银行", "中国平安", "宁德时代", "五粮液", "银行", "食品饮料"])


def _name_for_code(signals: list[dict], code: str) -> str:
    for signal in signals:
        if str(signal.get("stock_code")) == code:
            return str(signal.get("stock_name") or code)
    return code


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _all_layer_candidates(layers: dict[str, list[dict]]) -> list[dict]:
    output: list[dict] = []
    for items in layers.values():
        if isinstance(items, list):
            output.extend(items)
    return output


def _downgrade_mode(mode: str, floor: str | None = None) -> str:
    downgraded = {
        "PROBE": "WATCH",
        "WATCH": "DEFENSIVE_OBSERVE",
        "DEFENSIVE_OBSERVE": "RISK_OFF",
        "RISK_OFF": "WAIT",
        "WAIT": "WAIT",
    }.get(mode, "WATCH")
    if floor:
        ranks = {"WAIT": 0, "RISK_OFF": 1, "DEFENSIVE_OBSERVE": 2, "WATCH": 3, "PROBE": 4}
        if ranks.get(downgraded, 0) < ranks.get(floor, 0):
            return floor
    return downgraded


def _normalize_decision_controls(
    mode: str,
    position: tuple[float, float],
    allowed: list[str],
    forbidden: list[str],
) -> tuple[tuple[float, float], list[str], list[str]]:
    if mode == "WAIT":
        return (
            (0.0, 0.0),
            ["复盘风险候选", "检查数据质量"],
            ["短线追涨", "龙头接力", "趋势突破", "扩大仓位"],
        )
    if mode == "RISK_OFF":
        return (
            (0.0, 0.0),
            ["风险跟踪", "复盘候选", "检查策略参数"],
            ["新增进攻观察", "短线热点追涨", "龙头接力", "扩大仓位"],
        )
    return position, allowed, forbidden


def _decision_text(mode: str, regime: str, position: tuple[float, float], reasons: list[str]) -> str:
    labels = {
        "WAIT": "等待",
        "DEFENSIVE_OBSERVE": "防御观察",
        "WATCH": "谨慎观察",
        "PROBE": "小仓试探",
        "RISK_OFF": "风险关闭",
    }
    reason_text = "，".join(reasons[:2]) if reasons else "策略信号仍需人工确认"
    return f"今日模式为{labels.get(mode, mode)}，市场状态 {regime}，建议总仓位 {position[0]:.0%} ~ {position[1]:.0%}。{reason_text}。"


def _decision_guidance(
    mode: str,
    regime: str,
    layers: dict[str, list[dict]],
    strategy_health: list[dict],
    high_risk_ratio: float,
    average_score: float,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    market_context = market_context or {}
    main_count = len(layers.get("mainWatchlist", []))
    effective_count = sum(1 for item in strategy_health if item.get("status") == "有效")
    why = []
    if market_context.get("overrideReason"):
        why.append(str(market_context["overrideReason"]))
    if mode == "WAIT":
        why.append(f"当前市场状态为 {regime}，主观察清单 {main_count} 只。")
        if main_count == 0:
            why.append("主观察清单为空，今日没有可作为行动依据的候选。")
        if high_risk_ratio > 0.5:
            why.append("高风险候选比例超过 50%，策略信号质量不足。")
        if average_score < 50:
            why.append("多策略平均分低于 50，系统自动降级为等待和复盘。")
    else:
        why.append(f"当前模式为 {mode}，由市场状态、候选质量和风险比例共同决定。")
        if regime in {"Recovery", "RiskOn"}:
            why.append("市场状态已进入修复或进攻区间，允许观察主线强势、趋势突破和放量强势标的。")
    waiting_signals = [
        "市场状态从 RiskOff 改善到 Choppy 或 Recovery",
        "主观察清单至少出现 1 只低/中风险标的",
        "高风险候选比例下降到 50% 以下",
        "至少 1 个策略从“仅复盘”恢复为“有效”",
    ]
    return {
        "whyCurrentMode": why,
        "waitingSignals": waiting_signals,
        "switchConditions": {
            "toDefensiveObserve": [
                "市场仍为 RiskOff，但出现低/中风险的低波防御、质量动量或低回撤候选",
                "风险观察池比例下降，高风险候选不再占主导",
                "数据质量无新增严重风险",
            ],
            "toWatch": [
                "市场状态改善到 Choppy 或 Recovery",
                "主观察清单至少 1 只，且风险等级为低或中",
                "至少 1 个策略状态为“有效”，且平均分不低于 50",
            ],
            "toProbe": [
                "市场状态为 RiskOn 或 Recovery",
                "主观察清单不少于 3 只，且高风险候选比例低于 30%",
                "有效策略不少于 3 个，热点和趋势数据质量可用",
            ],
        },
    }


def _critical_hotspot_data_missing(coverage: dict | None) -> bool:
    return bool((coverage or {}).get("criticalHotspotDataMissing"))


def _theme_data_basis(coverage: dict) -> list[str]:
    return [item["name"] for item in coverage.get("items", []) if item.get("status") in {"已接入", "降级估算"}]


def _theme_missing_data(coverage: dict) -> list[str]:
    return [item["name"] for item in coverage.get("items", []) if item.get("status") == "缺失"]
