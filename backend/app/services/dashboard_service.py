from __future__ import annotations

from app.core.config import DISCLAIMER
from app.db.database import dict_from_row, dicts_from_rows, get_connection
from app.services.analytics import enrich_prices
from app.services.backtest_service import check_backtest_validity
from app.services.classic_quant import market_regime_model, portfolio_risk_budget
from app.services.decision_engine import (
    build_daily_decision,
    data_coverage_panel,
    data_quality_panel,
    detect_market_themes,
    evaluate_candidate_diversity,
    evaluate_missed_opportunity_risk,
    evaluate_strategy_health,
    split_candidate_layers,
)
from app.services.hotspot_data_provider import get_market_snapshot
from app.services.market_service import get_prices
from app.services.review_service import list_reviews
from app.services.risk_service import risk_overview
from app.services.strategy_service import list_signals, list_strategies
from app.services.strategy_source_service import summarize_strategy_sources


def dashboard_summary() -> dict:
    today_signals = list_signals(only_today=True)
    risk = risk_overview()
    market_context = _market_regime_context()
    strategies = list_strategies()
    data_coverage = data_coverage_panel(market_context)
    market_theme = detect_market_themes(market_context, today_signals, data_coverage)
    candidate_layers = split_candidate_layers(today_signals, market_context["marketRegime"], market_theme=market_theme)
    candidate_funnel = _candidate_funnel(market_context, today_signals, candidate_layers)
    latest_backtests_by_strategy = _latest_backtests_by_strategy()
    strategy_health = evaluate_strategy_health(
        today_signals,
        strategies,
        market_context["marketRegime"],
        critical_hotspot_data_missing=data_coverage["criticalHotspotDataMissing"],
        latest_backtests=latest_backtests_by_strategy,
    )
    strategy_distribution = _strategy_distribution(today_signals, strategy_health)
    daily_decision = build_daily_decision(
        market_context.get("tradeDate") or _latest_trade_date(),
        market_context["marketRegime"],
        candidate_layers,
        strategy_health,
        market_context=market_context,
    )
    diversity = evaluate_candidate_diversity(today_signals)
    missed_opportunity = evaluate_missed_opportunity_risk(market_context["marketRegime"], candidate_layers, market_theme, candidate_funnel)
    data_quality = data_quality_panel(market_context)
    strategy_candidates = [
        signal["strategyCandidate"]
        for signal in today_signals
        if signal.get("strategyCandidate")
    ]
    portfolio_budget = portfolio_risk_budget(strategy_candidates, market_context["marketRegime"])
    with get_connection() as conn:
        latest_price = conn.execute("SELECT MAX(date) AS date FROM daily_prices").fetchone()["date"]
        latest_signal = conn.execute("SELECT MAX(created_at) AS created_at FROM signals").fetchone()["created_at"]
        latest_backtest = conn.execute(
            """
            SELECT
                br.id,
                br.strategy_id,
                br.start_date,
                br.end_date,
                br.total_return,
                br.annual_return,
                br.max_drawdown,
                br.sharpe,
                br.win_rate,
                br.trade_count,
                br.created_at,
                st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            ORDER BY br.created_at DESC
            LIMIT 1
            """
        ).fetchone()
        market = conn.execute(
            """
            SELECT
                AVG(dp.pct_change) AS avg_change,
                SUM(CASE WHEN dp.pct_change > 0 THEN 1 ELSE 0 END) AS up_count,
                COUNT(*) AS total_count
            FROM daily_prices dp
            WHERE dp.date = (SELECT MAX(date) FROM daily_prices)
            """
        ).fetchone()
        backtests = conn.execute(
            """
            SELECT br.id, br.created_at, br.total_return, br.max_drawdown, br.win_rate, st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            ORDER BY br.created_at DESC
            LIMIT 8
            """
        ).fetchall()

    strategy_status = []
    for strategy in strategies:
        count = len([signal for signal in today_signals if signal["strategy_id"] == strategy["id"]])
        strategy_status.append(
            {
                "id": strategy["id"],
                "name": strategy["name"],
                "type": strategy["type"],
                "enabled": strategy["enabled"],
                "today_signal_count": count,
            }
        )

    backtest = dict_from_row(latest_backtest) if latest_backtest else None
    if backtest:
        backtest["result_json"] = {}
        backtest["validity"] = check_backtest_validity(backtest)
    market_status = {
        "avg_change": round(float(market["avg_change"] or 0), 2) if market else 0,
        "up_count": int(market["up_count"] or 0) if market else 0,
        "total_count": int(market["total_count"] or 0) if market else 0,
    }
    if market_status["avg_change"] > 0.6:
        market_status["summary"] = "样本市场偏强"
    elif market_status["avg_change"] < -0.6:
        market_status["summary"] = "样本市场偏弱"
    else:
        market_status["summary"] = "样本市场震荡"

    current_risk_level = "high" if risk["high_risk_count"] else "medium" if risk["medium_risk_count"] else "low"
    return {
        "last_data_date": latest_price,
        "last_run_time": latest_signal,
        "candidate_count": len(today_signals),
        "market_status": market_status,
        "market_regime": market_context,
        "daily_decision": daily_decision,
        "position_decision": daily_decision["positionDecision"],
        "candidate_funnel": candidate_funnel,
        "candidate_layers": candidate_layers,
        "strategy_health": strategy_health,
        "strategy_source_summary": summarize_strategy_sources(),
        "strategy_decision_status": _strategy_decision_status(strategy_health),
        "candidate_diversity": diversity,
        "missed_opportunity_risk": missed_opportunity,
        "market_theme": market_theme,
        "data_coverage": data_coverage,
        "data_quality": data_quality,
        "strategy_status": strategy_status,
        "strategy_distribution": strategy_distribution,
        "portfolio_risk_budget": portfolio_budget,
        "latest_backtest": backtest,
        "current_risk_level": current_risk_level,
        "watchlist": candidate_layers["mainWatchlist"][:8],
        "defensive_watchlist": candidate_layers["defensiveWatchlist"][:8],
        "hotspot_watchlist": candidate_layers["hotspotWatchlist"][:8],
        "risk_pool": candidate_layers["riskPool"][:8],
        "review_pool": candidate_layers["reviewPool"][:8],
        "risk_alerts": risk["warnings"],
        "recent_backtests": [_with_backtest_validity(item) for item in dicts_from_rows(backtests)],
        "recent_reviews": list_reviews(limit=5),
        "disclaimer": DISCLAIMER,
    }


def _market_regime_context() -> dict:
    with get_connection() as conn:
        stocks = dicts_from_rows(
            conn.execute(
                """
                SELECT code, name, industry, market, list_date, is_st, is_suspended, float_market_cap
                FROM stocks
                ORDER BY code
                """
            ).fetchall()
        )
        trade_date = conn.execute("SELECT MAX(date) AS date FROM daily_prices").fetchone()["date"]
    frames = [{"stock": stock, "frame": enrich_prices(get_prices(stock["code"], limit=140))} for stock in stocks]
    snapshot = get_market_snapshot(trade_date)
    context = market_regime_model(frames, trade_date, market_snapshot=snapshot.get("data") if snapshot.get("ready") else None)
    context["tradeDate"] = trade_date
    context["marketSnapshot"] = snapshot
    return context


def _latest_trade_date() -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(date) AS date FROM daily_prices").fetchone()
    return row["date"] if row else None


def _strategy_distribution(signals: list[dict], health: list[dict] | None = None) -> list[dict]:
    health_by_name = {item["strategyName"]: item for item in health or []}
    grouped: dict[str, list[dict]] = {}
    for signal in signals:
        grouped.setdefault(signal["strategy_name"], []).append(signal)
    distribution = []
    for name, items in grouped.items():
        distribution.append(
            {
                "strategyName": name,
                "candidateCount": len(items),
                "highRiskCount": sum(1 for item in items if item["risk_level"] == "high"),
                "averageScore": round(sum(float(item["score"] or 0) for item in items) / max(len(items), 1), 2),
                "filteredCount": 0,
                "status": health_by_name.get(name, {}).get("status", "有效"),
                "reason": health_by_name.get(name, {}).get("reason", ""),
                "mainCount": health_by_name.get(name, {}).get("mainCount", 0),
                "highRiskRatio": health_by_name.get(name, {}).get("highRiskRatio", 0),
                "backtestValidity": health_by_name.get(name, {}).get("backtestValidity"),
                "latestBacktestTradeCount": health_by_name.get(name, {}).get("latestBacktestTradeCount"),
            }
        )
    return sorted(distribution, key=lambda item: item["candidateCount"], reverse=True)


def _candidate_funnel(market_context: dict, signals: list[dict], layers: dict[str, list[dict]]) -> dict:
    total_stock_count = int(market_context.get("totalStockCount") or 0)
    hard_risk_count = len([signal for signal in signals if signal.get("hardRisk")])
    final_actionable = (
        len(layers.get("mainWatchlist", []))
        + len(layers.get("defensiveWatchlist", []))
        + len(layers.get("hotspotWatchlist", []))
    )
    strategy_initial = len(signals)
    risk_count = len(layers.get("riskPool", []))
    review_count = len(layers.get("reviewPool", []))
    non_theme_count = len(
        [
            signal
            for signal in signals
            if signal.get("risk_level") != "high"
            and signal.get("suggestedAction") != "暂不参与"
            and signal not in layers.get("mainWatchlist", [])
            and signal not in layers.get("defensiveWatchlist", [])
            and signal not in layers.get("hotspotWatchlist", [])
            and signal not in layers.get("riskPool", [])
        ]
    )
    data_missing_count = len([signal for signal in signals if any("数据" in reason or "题材数据暂缺" in reason for reason in signal.get("triggerReasons", []) + signal.get("riskReasons", []))])
    breakdown = [
        _funnel_stage("初筛候选", strategy_initial, strategy_initial),
        _funnel_stage("风控剔除/风险池", risk_count, strategy_initial),
        _funnel_stage("回测无效/仅复盘", review_count, strategy_initial),
        _funnel_stage("非主线或强度不足", non_theme_count, strategy_initial),
        _funnel_stage("数据缺失降级", data_missing_count, strategy_initial),
        _funnel_stage("最终可行动", final_actionable, strategy_initial),
    ]
    return {
        "rawStockPool": total_stock_count,
        "baseFiltered": max(total_stock_count - hard_risk_count, 0),
        "strategyInitialCandidates": len(signals),
        "hardRiskFiltered": hard_risk_count,
        "riskPool": len(layers.get("riskPool", [])),
        "defensiveWatchlist": len(layers.get("defensiveWatchlist", [])),
        "hotspotWatchlist": len(layers.get("hotspotWatchlist", [])),
        "mainWatchlist": len(layers.get("mainWatchlist", [])),
        "finalActionableCandidates": final_actionable,
        "filterBreakdown": breakdown,
    }


def _funnel_stage(name: str, count: int, total: int) -> dict:
    ratio = count / total if total else 0
    return {
        "name": name,
        "count": count,
        "ratio": round(ratio, 4),
        "warning": ratio > 0.7 and name not in {"初筛候选", "最终可行动"},
    }


def _strategy_decision_status(health: list[dict]) -> dict:
    return {
        "activeStrategies": len([item for item in health if item.get("status") == "有效"]),
        "observeOnlyStrategies": len([item for item in health if item.get("status") == "降权"]),
        "reviewOnlyStrategies": len([item for item in health if item.get("status") == "仅复盘"]),
        "pausedStrategies": len([item for item in health if item.get("status") == "暂停"]),
    }


def _latest_backtests_by_strategy() -> dict[str, dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT br.*, st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            WHERE br.id IN (
                SELECT MAX(id)
                FROM backtest_results
                GROUP BY strategy_id
            )
            """
        ).fetchall()
    output: dict[str, dict] = {}
    for row in dicts_from_rows(rows):
        item = _with_backtest_validity(row)
        output[str(item["strategy_name"])] = item
    return output


def _with_backtest_validity(item: dict) -> dict:
    item["result_json"] = {}
    item["validity"] = check_backtest_validity(item)
    return item
