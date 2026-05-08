from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services.classic_quant import (
    evaluate_classic_strategy,
    is_classic_quant_strategy,
    market_regime_model,
)
from app.services.dragon_leader_strategy import (
    evaluate_dragon_leader,
    evaluate_dragon_observation_candidate,
    is_dragon_strategy,
    prepare_dragon_context,
)
from app.services.hotspot_data_provider import get_market_snapshot
from app.services.analytics import enrich_prices, safe_float
from app.services.market_service import get_prices, latest_trade_date
from app.services.strategy_rules import evaluate_strategy_row, parse_parameters

MAX_SIGNALS_PER_STRATEGY = 20


def list_strategies() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM strategies ORDER BY id").fetchall()
    strategies = dicts_from_rows(rows)
    from app.services.strategy_source_service import list_strategy_sources

    sources = {source["strategyName"]: source for source in list_strategy_sources()}
    for strategy in strategies:
        strategy["parameters"] = parse_parameters(strategy.get("parameters"))
        strategy["enabled"] = bool(strategy["enabled"])
        strategy["source"] = sources.get(strategy["name"])
    return strategies


def get_strategy(strategy_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    strategy = dict_from_row(row)
    if strategy:
        strategy["parameters"] = parse_parameters(strategy.get("parameters"))
        strategy["enabled"] = bool(strategy["enabled"])
        from app.services.strategy_source_service import get_strategy_source

        strategy["source"] = get_strategy_source(strategy["name"])
    return strategy


def create_strategy(payload: dict[str, Any]) -> dict:
    timestamp = now_iso()
    parameters = payload.get("parameters") or {}
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["name"],
                payload.get("description", ""),
                payload.get("type", "多因子"),
                json.dumps(parameters, ensure_ascii=False),
                1 if payload.get("enabled", True) else 0,
                timestamp,
                timestamp,
            ),
        )
    return get_strategy(cursor.lastrowid) or {}


def update_strategy(strategy_id: int, payload: dict[str, Any]) -> dict | None:
    current = get_strategy(strategy_id)
    if not current:
        return None
    updated = {
        "name": payload.get("name", current["name"]),
        "description": payload.get("description", current["description"]),
        "type": payload.get("type", current["type"]),
        "parameters": payload.get("parameters", current["parameters"]),
        "enabled": payload.get("enabled", current["enabled"]),
    }
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE strategies
            SET name = ?, description = ?, type = ?, parameters = ?, enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["description"],
                updated["type"],
                json.dumps(updated["parameters"], ensure_ascii=False),
                1 if updated["enabled"] else 0,
                now_iso(),
                strategy_id,
            ),
        )
    return get_strategy(strategy_id)


def run_strategies(strategy_id: int | None = None) -> dict:
    trade_date = latest_trade_date()
    if not trade_date:
        return {"trade_date": None, "signals_created": 0, "strategies_run": 0}

    strategies = [get_strategy(strategy_id)] if strategy_id else list_strategies()
    active_strategies = [strategy for strategy in strategies if strategy and (strategy_id or strategy.get("enabled"))]
    stocks = _stocks_for_scan()
    market_volatility = _market_volatility(stocks)
    price_cache: dict[str, Any] = {}
    for stock in stocks:
        price_cache[stock["code"]] = enrich_prices(get_prices(stock["code"], limit=140))
    dragon_context = prepare_dragon_context(
        [{"stock": stock, "frame": price_cache[stock["code"]]} for stock in stocks if not price_cache[stock["code"]].empty],
        trade_date,
    )
    market_snapshot = get_market_snapshot(trade_date)
    market_context = market_regime_model(
        [{"stock": stock, "frame": price_cache[stock["code"]]} for stock in stocks if not price_cache[stock["code"]].empty],
        trade_date,
        market_snapshot=(market_snapshot.get("data") if market_snapshot.get("ready") else None),
    )
    market_context["marketSnapshot"] = market_snapshot
    created_count = 0
    timestamp = now_iso()
    run_logs: list[dict] = []

    with get_connection() as conn:
        if strategy_id:
            conn.execute("DELETE FROM signals WHERE date = ? AND strategy_id = ?", (trade_date, strategy_id))
        else:
            conn.execute("DELETE FROM signals WHERE date = ?", (trade_date,))

        for strategy in active_strategies:
            dragon_log = {
                "strategy_id": strategy["id"],
                "strategy_name": strategy["name"],
                "raw_stock_count": len(stocks),
                "base_filter_count": 0,
                "limit_or_breakout_count": 0,
                "sector_linkage_count": 0,
                "final_candidate_count": 0,
                "high_risk_filtered_count": 0,
                "market_sentiment": dragon_context.get("marketSentiment"),
                "high_board_height": dragon_context.get("highBoardHeight"),
                "market_limit_up_count": dragon_context.get("marketLimitUpCount"),
                "market_limit_down_count": dragon_context.get("marketLimitDownCount"),
            }
            strategy_candidates: list[tuple[str, dict]] = []
            dragon_observation_candidates: list[tuple[str, dict]] = []
            for stock in stocks:
                enriched = price_cache[stock["code"]]
                if enriched.empty or len(enriched) < 60:
                    continue
                latest = enriched.iloc[-1]
                if is_classic_quant_strategy(strategy):
                    signal = evaluate_classic_strategy(strategy, stock, enriched, market_context)
                    if signal:
                        strategy_candidates.append((stock["code"], signal))
                elif is_dragon_strategy(strategy):
                    signal, diagnostics = evaluate_dragon_leader(strategy, stock, enriched, dragon_context)
                    if diagnostics.base_filter_passed:
                        dragon_log["base_filter_count"] += 1
                    if diagnostics.hit_limit_or_breakout:
                        dragon_log["limit_or_breakout_count"] += 1
                    if diagnostics.hit_sector_linkage:
                        dragon_log["sector_linkage_count"] += 1
                    if signal:
                        strategy_candidates.append((stock["code"], signal))
                    else:
                        observation_signal, observation_diagnostics = evaluate_dragon_observation_candidate(
                            strategy,
                            stock,
                            enriched,
                            dragon_context,
                        )
                        if observation_diagnostics.final_candidate and observation_signal:
                            dragon_observation_candidates.append((stock["code"], observation_signal))
                else:
                    signal = evaluate_strategy_row(strategy, latest, market_volatility, relaxed=True, market_context=market_context)
                    if signal:
                        strategy_candidates.append((stock["code"], signal))

            if is_dragon_strategy(strategy) and not strategy_candidates:
                strategy_candidates = dragon_observation_candidates
            strategy_candidates = sorted(
                strategy_candidates,
                key=lambda item: float(item[1].get("score") or 0),
                reverse=True,
            )[:MAX_SIGNALS_PER_STRATEGY]
            if is_dragon_strategy(strategy):
                dragon_log["final_candidate_count"] = len(strategy_candidates)
                dragon_log["high_risk_filtered_count"] = sum(
                    1 for _code, signal in strategy_candidates if signal.get("risk_level") == "high"
                )

            for stock_code, signal in strategy_candidates:
                conn.execute(
                    """
                    INSERT INTO signals
                        (date, stock_code, strategy_id, signal_type, score, reason, risk_reason, risk_level, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade_date,
                        stock_code,
                        strategy["id"],
                        signal["signal_type"],
                        signal["score"],
                        signal["reason"],
                        signal["risk_reason"],
                        signal["risk_level"],
                        json.dumps(signal.get("metadata", {}), ensure_ascii=False),
                        timestamp,
                    ),
                )
                created_count += 1
            if is_dragon_strategy(strategy):
                run_logs.append(dragon_log)

    return {
        "trade_date": trade_date,
        "signals_created": created_count,
        "strategies_run": len(active_strategies),
        "created_at": timestamp,
        "logs": run_logs,
    }


def list_signals(
    only_today: bool = False,
    search: str | None = None,
    industry: str | None = None,
    strategy_id: int | None = None,
    risk_level: str | None = None,
    suggested_action: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if only_today:
        trade_date = latest_trade_date()
        if trade_date:
            clauses.append("sig.date = ?")
            params.append(trade_date)
    if search:
        clauses.append("(sig.stock_code LIKE ? OR s.name LIKE ?)")
        keyword = f"%{search}%"
        params.extend([keyword, keyword])
    if industry and industry != "all":
        clauses.append("s.industry = ?")
        params.append(industry)
    if strategy_id:
        clauses.append("sig.strategy_id = ?")
        params.append(strategy_id)
    if risk_level and risk_level != "all":
        clauses.append("sig.risk_level = ?")
        params.append(risk_level)
    if suggested_action and suggested_action != "all":
        clauses.append("json_extract(sig.metadata, '$.suggestedAction') = ?")
        params.append(suggested_action)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = "LIMIT ?" if limit else ""
    if limit:
        params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                sig.*,
                s.name AS stock_name,
                s.industry,
                s.market,
                st.name AS strategy_name,
                st.type AS strategy_type,
                COALESCE(dp_signal.close, dp_latest.close) AS current_price,
                COALESCE(dp_signal.pct_change, dp_latest.pct_change) AS pct_change,
                COALESCE(dp_signal.date, dp_latest.date) AS price_date,
                bt.total_return AS recent_backtest_return,
                bt.max_drawdown AS recent_backtest_drawdown
            FROM signals sig
            JOIN stocks s ON s.code = sig.stock_code
            JOIN strategies st ON st.id = sig.strategy_id
            LEFT JOIN daily_prices dp_signal
                ON dp_signal.stock_code = sig.stock_code
               AND dp_signal.date = sig.date
            LEFT JOIN daily_prices dp_latest
                ON dp_latest.stock_code = sig.stock_code
               AND dp_latest.date = (SELECT MAX(date) FROM daily_prices WHERE stock_code = sig.stock_code)
            LEFT JOIN backtest_results bt
                ON bt.id = (
                    SELECT id
                    FROM backtest_results
                    WHERE strategy_id = sig.strategy_id
                    ORDER BY created_at DESC
                    LIMIT 1
                )
            {where_sql}
            ORDER BY
                sig.date DESC,
                CASE json_extract(sig.metadata, '$.suggestedAction')
                    WHEN '谨慎观察' THEN 0
                    WHEN '观察' THEN 1
                    ELSE 2
                END,
                CASE sig.risk_level
                    WHEN 'low' THEN 0
                    WHEN 'medium' THEN 1
                    ELSE 2
                END,
                CASE json_extract(sig.metadata, '$.candidateLevel')
                    WHEN '核心候选' THEN 0
                    WHEN '热点核心候选' THEN 0
                    WHEN '强势候选' THEN 1
                    WHEN '热点强势候选' THEN 1
                    ELSE 2
                END,
                CAST(COALESCE(json_extract(sig.metadata, '$.strategyConfidence'), sig.score) AS REAL) DESC,
                sig.score DESC
            {limit_sql}
            """,
            params,
        ).fetchall()

    signals = dicts_from_rows(rows)
    for signal in signals:
        _decorate_signal(signal)
    _apply_diversity_penalty(signals)
    return signals


def get_signal(signal_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT sig.*, s.name AS stock_name, s.industry, st.name AS strategy_name
            FROM signals sig
            JOIN stocks s ON s.code = sig.stock_code
            JOIN strategies st ON st.id = sig.strategy_id
            WHERE sig.id = ?
            """,
            (signal_id,),
        ).fetchone()
    signal = dict_from_row(row)
    if signal:
        _decorate_signal(signal)
    return signal


def _stocks_for_scan() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT code, name, industry, market, list_date, is_st, is_suspended, float_market_cap
            FROM stocks
            ORDER BY code
            """
        ).fetchall()
    return dicts_from_rows(rows)


def _market_volatility(stocks: list[dict]) -> float:
    values: list[float] = []
    for stock in stocks:
        enriched = enrich_prices(get_prices(stock["code"], limit=120))
        if enriched.empty:
            continue
        values.append(safe_float(enriched.iloc[-1].get("volatility_60")))
    values = [value for value in values if value > 0]
    return sum(values) / len(values) if values else 0.03


def _decorate_signal(signal: dict) -> None:
    metadata = _parse_metadata(signal.get("metadata"))
    signal["metadata"] = metadata
    if metadata.get("strategyClass") == "DragonLeaderStrategy":
        signal["dragon"] = metadata
        signal["dragonScore"] = metadata.get("dragonScore")
        signal["candidateLevel"] = metadata.get("candidateLevel")
        signal["candidateTypes"] = metadata.get("candidateTypes", ["龙头候选", "短线强势"])
        signal["suggestedAction"] = metadata.get("suggestedAction")
        signal["triggerReasons"] = metadata.get("triggerReasons", [])
        signal["riskReasons"] = metadata.get("riskReasons", [])
        signal["exitRules"] = metadata.get("exitRules", [])
        signal["marketSentiment"] = metadata.get("marketSentiment")
        signal["marketRegime"] = metadata.get("marketRegime")
    elif metadata.get("strategyCandidate"):
        candidate = metadata["strategyCandidate"]
        signal["strategyCandidate"] = candidate
        signal["candidateLevel"] = metadata.get("candidateLevel")
        signal["candidateTypes"] = candidate.get("candidateTypes", metadata.get("candidateTypes", []))
        signal["suggestedAction"] = candidate.get("suggestedAction")
        signal["suggestedWeight"] = candidate.get("suggestedWeight")
        signal["maxPosition"] = candidate.get("maxPosition")
        signal["marketRegime"] = candidate.get("marketRegime")
        signal["triggerReasons"] = candidate.get("triggerReasons", [])
        signal["riskReasons"] = candidate.get("riskReasons", [])
        signal["exitRules"] = candidate.get("exitRules", [])
        signal["subScores"] = candidate.get("subScores", {})
        signal["hotspotScore"] = candidate.get("hotspotScore")
        signal["sectorHotScore"] = candidate.get("sectorHotScore")
        signal["leaderScore"] = candidate.get("leaderScore")
        signal["capitalFlowScore"] = candidate.get("capitalFlowScore")
        signal["volumeRatio"] = candidate.get("volumeRatio")
        signal["turnoverRate"] = candidate.get("turnoverRate")
        signal["amount"] = candidate.get("amount")
    else:
        signal["candidateLevel"] = metadata.get("candidateLevel")
        signal["candidateTypes"] = metadata.get("candidateTypes", [])
        signal["suggestedAction"] = metadata.get("suggestedAction")
        signal["triggerReasons"] = metadata.get("triggerReasons", [])
        signal["riskReasons"] = metadata.get("riskReasons", [])
        signal["exitRules"] = metadata.get("exitRules", [])
        signal["marketRegime"] = metadata.get("marketRegime")
    signal["signalScore"] = metadata.get("signalScore", signal.get("score"))
    signal["riskPenalty"] = metadata.get("riskPenalty", 0)
    signal["finalScore"] = metadata.get("finalScore", signal.get("score"))
    signal["strategyConfidence"] = metadata.get("strategyConfidence", metadata.get("suggestedWeight", signal.get("score")))
    signal["candidateMode"] = metadata.get("candidateMode")
    signal["hardRisk"] = metadata.get("hardRisk", [])
    signal["softRisk"] = metadata.get("softRisk", [])
    if not signal.get("marketRegime"):
        signal["marketRegime"] = metadata.get("marketRegime")
    score = float(signal.get("score") or 0)
    risk_level = signal.get("risk_level", "medium")
    signal["trend_score"] = round(min(100, score + (4 if risk_level == "low" else -4 if risk_level == "high" else 0)), 2)
    signal["valuation_score"] = round(max(35, min(95, score - 6 + (3 if signal.get("industry") in {"银行", "食品饮料"} else 0))), 2)
    signal["capital_score"] = round(max(30, min(100, score + (float(signal.get("pct_change") or 0) * 1.2))), 2)
    if signal.get("recent_backtest_return") is not None:
        signal["recent_backtest_performance"] = f"收益 {float(signal['recent_backtest_return']):.1%} / 回撤 {float(signal.get('recent_backtest_drawdown') or 0):.1%}"
    else:
        signal["recent_backtest_performance"] = "暂无回测"
    if isinstance(signal.get("created_at"), datetime):
        signal["created_at"] = signal["created_at"].isoformat()


def _parse_metadata(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return {}


def _apply_diversity_penalty(signals: list[dict]) -> None:
    if not signals:
        return
    counts: dict[str, int] = {}
    for signal in signals:
        code = str(signal.get("stock_code"))
        counts[code] = counts.get(code, 0) + 1
    repeat_rate = 1 - len(counts) / max(len(signals), 1)
    if repeat_rate <= 0.7:
        return
    for signal in signals:
        appearances = counts.get(str(signal.get("stock_code")), 0)
        if appearances <= 1:
            signal["isNewCandidate"] = True
            continue
        penalty = min(15, 5 + appearances * 2)
        original_score = float(signal.get("score") or 0)
        signal["score"] = round(max(0, original_score - penalty), 2)
        signal["finalScore"] = round(max(0, float(signal.get("finalScore") or original_score) - penalty), 2)
        signal["strategyConfidence"] = round(max(0, float(signal.get("strategyConfidence") or original_score) - penalty), 2)
        signal["diversityPenalty"] = penalty
        reasons = list(signal.get("triggerReasons") or [])
        reason = "候选重复出现且评分未改善，降低优先级"
        if reason not in reasons:
            reasons.append(reason)
        signal["triggerReasons"] = reasons
