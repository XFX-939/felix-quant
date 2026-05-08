from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services.analytics import enrich_prices, equity_drawdown, safe_float
from app.services.classic_quant import evaluate_classic_strategy, is_classic_quant_strategy, market_regime_model
from app.services.dragon_leader_strategy import evaluate_dragon_leader, is_dragon_strategy, prepare_dragon_context
from app.services.market_service import get_prices
from app.services.strategy_rules import evaluate_strategy_row
from app.services.strategy_service import get_strategy


def run_backtest(payload: dict[str, Any]) -> dict:
    strategy_id = int(payload["strategy_id"])
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise ValueError("strategy not found")
    if is_dragon_strategy(strategy):
        return _run_dragon_backtest(strategy, payload)
    if is_classic_quant_strategy(strategy):
        return _run_classic_quant_backtest(strategy, payload)

    start_date = payload.get("start_date") or _default_start_date()
    end_date = payload.get("end_date") or _default_end_date()
    initial_cash = float(payload.get("initial_cash", 100000))
    fee_rate = float(payload.get("fee_rate", 0.0003))
    slippage = float(payload.get("slippage", 0.001) or 0.001)
    stop_loss = float(payload.get("stop_loss", 0.08))
    position_cap = float(payload.get("position_cap", 0.2))
    stock_pool = payload.get("stock_pool", "all")
    codes = _resolve_stock_pool(stock_pool, strategy_id)

    daily_candidates: dict[str, list[dict]] = defaultdict(list)
    market_volatility = _market_volatility(codes)

    for code in codes:
        prices = get_prices(code, start_date=start_date, end_date=end_date)
        enriched = enrich_prices(prices)
        if enriched.empty or len(enriched) < 65:
            continue
        for idx in range(60, len(enriched) - 1):
            row = enriched.iloc[idx]
            next_row = enriched.iloc[idx + 1]
            signal = evaluate_strategy_row(strategy, row, market_volatility)
            if not signal:
                continue
            one_day_return = safe_float(next_row["close"] / row["close"] - 1)
            one_day_return = max(one_day_return, -abs(stop_loss))
            daily_candidates[next_row["date"].date().isoformat()].append(
                {
                    "date": next_row["date"].date().isoformat(),
                    "stock_code": code,
                    "score": signal["score"],
                    "return": one_day_return,
                    "reason": signal["reason"],
                    "risk_level": signal["risk_level"],
                }
            )

    all_dates = sorted(daily_candidates.keys())
    cash = initial_cash
    equity_curve: list[dict] = []
    daily_returns: list[float] = []
    trades: list[dict] = []

    for trade_date in all_dates:
        picks = sorted(daily_candidates[trade_date], key=lambda item: item["score"], reverse=True)
        if not picks:
            portfolio_return = 0.0
        else:
            weight = min(position_cap, 1 / len(picks))
            gross_return = sum(weight * pick["return"] for pick in picks)
            portfolio_return = gross_return - (fee_rate + slippage) * weight * len(picks)
            for pick in picks:
                trades.append(
                    {
                        "date": trade_date,
                        "stock_code": pick["stock_code"],
                        "action": "模拟持有",
                        "score": round(pick["score"], 2),
                        "return": round(pick["return"], 4),
                        "weight": round(weight, 4),
                        "reason": pick["reason"],
                        "risk_level": pick["risk_level"],
                    }
                )
        cash *= 1 + portfolio_return
        daily_returns.append(portfolio_return)
        equity_curve.append({"date": trade_date, "value": round(cash, 2), "return": round(portfolio_return, 5)})

    if not equity_curve:
        equity_curve = [{"date": end_date, "value": initial_cash, "return": 0}]
        daily_returns = [0.0]

    drawdown_values = equity_drawdown([point["value"] for point in equity_curve])
    drawdown_curve = [
        {"date": point["date"], "value": round(drawdown, 5)}
        for point, drawdown in zip(equity_curve, drawdown_values, strict=False)
    ]
    final_value = equity_curve[-1]["value"]
    total_return = final_value / initial_cash - 1
    periods = max(1, len(equity_curve))
    annual_return = (final_value / initial_cash) ** (252 / periods) - 1 if final_value > 0 else -1
    max_drawdown = abs(min(drawdown_values)) if drawdown_values else 0
    mean_return = float(np.mean(daily_returns))
    std_return = float(np.std(daily_returns))
    sharpe = (mean_return / std_return * math.sqrt(252)) if std_return > 0 else 0
    winning_returns = [item["return"] for item in trades if item["return"] > 0]
    losing_returns = [abs(item["return"]) for item in trades if item["return"] < 0]
    win_rate = len(winning_returns) / len(trades) if trades else 0
    profit_loss_ratio = (sum(winning_returns) / len(winning_returns)) / (sum(losing_returns) / len(losing_returns)) if winning_returns and losing_returns else 0

    result_json = {
        "stock_pool": stock_pool,
        "stock_count": len(codes),
        "initial_cash": initial_cash,
        "fee_rate": fee_rate,
        "slippage": slippage,
        "stop_loss": stop_loss,
        "position_cap": position_cap,
        "profit_loss_ratio": round(profit_loss_ratio, 4),
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trades": trades,
    }
    timestamp = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO backtest_results
                (strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                 sharpe, win_rate, trade_count, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                start_date,
                end_date,
                round(total_return, 6),
                round(annual_return, 6),
                round(max_drawdown, 6),
                round(sharpe, 6),
                round(win_rate, 6),
                len(trades),
                json.dumps(result_json, ensure_ascii=False),
                timestamp,
            ),
        )
    return get_backtest_result(cursor.lastrowid) or {}


def list_backtest_results(limit: int = 20, include_detail: bool = True) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT br.*, st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            ORDER BY br.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = dicts_from_rows(rows)
    for result in results:
        result_json = json.loads(result["result_json"])
        result["result_json"] = result_json if include_detail else _summarize_result_json(result_json)
        result["validity"] = check_backtest_validity(result)
    return results


def get_latest_backtest_result() -> dict | None:
    results = list_backtest_results(limit=1)
    return results[0] if results else None


def get_backtest_defaults() -> dict[str, Any]:
    latest_trade_date = _default_end_date()
    trade_dates = _trading_dates_until(latest_trade_date)
    periods = {
        "1M": _start_date_by_trading_days(trade_dates, 20, latest_trade_date),
        "3M": _start_date_by_trading_days(trade_dates, 60, latest_trade_date),
        "6M": _start_date_by_trading_days(trade_dates, 120, latest_trade_date),
        "1Y": _start_date_by_trading_days(trade_dates, 250, latest_trade_date),
        "2Y": _start_date_by_trading_days(trade_dates, 500, latest_trade_date),
    }
    with get_connection() as conn:
        signal_count = conn.execute("SELECT COUNT(*) AS c FROM signals WHERE date = (SELECT MAX(date) FROM signals)").fetchone()["c"]
    return {
        "latestTradeDate": latest_trade_date,
        "periods": periods,
        "defaultPeriod": "1Y",
        "defaultStockPool": "today_candidates" if signal_count else "sample",
        "usesTradingCalendar": bool(trade_dates),
    }


def get_backtest_result(result_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT br.*, st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            WHERE br.id = ?
            """,
            (result_id,),
        ).fetchone()
    result = dict_from_row(row)
    if result:
        result["result_json"] = json.loads(result["result_json"])
        result["validity"] = check_backtest_validity(result)
    return result


def delete_backtest_result(result_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM backtest_results WHERE id = ?", (result_id,))
        return cursor.rowcount > 0


def get_batch_backtest_detail(task_id: int) -> dict[str, Any] | None:
    from app.services import task_service

    task = task_service.get_task_run(task_id)
    if not task or task.get("task_type") != "batch_backtest":
        return None
    children = task_service.list_child_task_runs(task_id)
    summary = task.get("summary_json") or {}
    result_rows = summary.get("results") or []
    nav_series = [
        {
            "strategyName": item.get("strategyName"),
            "points": [
                {
                    "date": point.get("date"),
                    "value": point.get("value"),
                    "return": point.get("return"),
                    "cumulativeReturn": (float(point.get("value") or 0) / float((item.get("equityCurve") or [{}])[0].get("value") or 1) - 1)
                    if (item.get("equityCurve") or [{}])[0].get("value")
                    else None,
                }
                for point in item.get("equityCurve") or []
            ],
        }
        for item in result_rows
        if item.get("status") == "success"
    ]
    return {
        "task": task,
        "childTasks": children,
        "summary": summary,
        "resultTable": result_rows,
        "navSeries": nav_series,
        "validity": summary.get("validity"),
    }


def check_backtest_validity(result: dict[str, Any]) -> dict[str, Any]:
    result_json = result.get("result_json") or {}
    trade_count = int(result.get("trade_count") or 0)
    backtest_days = _date_span_days(result.get("start_date"), result.get("end_date"))
    stock_pool = str(result_json.get("stock_pool") or "")
    stock_count = int(result_json.get("stock_count") or 0)
    data_coverage_ratio = float(result_json.get("data_coverage_ratio", 1.0))
    fee_included = bool(float(result_json.get("fee_rate") or 0) > 0)
    slippage_included = bool(float(result_json.get("slippage") or 0) > 0)
    st_suspension_delist_handled = bool(result_json.get("st_suspension_delist_handled"))
    financial_announcement_lag_handled = bool(result_json.get("financial_announcement_lag_handled"))
    is_sample_pool = stock_pool in {"sample", "demo", "example"} or (stock_pool == "all" and 0 < stock_count <= 12)
    survivor_bias_risk = is_sample_pool or not st_suspension_delist_handled
    forward_bias_risk = not financial_announcement_lag_handled
    warnings: list[str] = []
    repair_suggestions: list[str] = []
    if is_sample_pool:
        warnings.append("股票池为示例股票池，可能存在幸存者偏差。")
        repair_suggestions.append("切换为全市场股票池或真实候选池后重新回测。")
    if trade_count < 30:
        warnings.append("交易次数不足 30，本次回测不具备统计意义。")
        repair_suggestions.append("扩大回测区间或增加真实股票池样本。")
    if backtest_days < 250:
        warnings.append("回测区间不足一年，结果仅供功能验证。")
        repair_suggestions.append("使用近一年或近两年区间进行策略有效性验证。")
    if data_coverage_ratio < 0.8:
        warnings.append("该周期行情或净值覆盖率不足 80%。")
        repair_suggestions.append("先补齐历史行情数据，再重新运行回测。")
    if not fee_included:
        warnings.append("未计入手续费，收益可能被高估。")
        repair_suggestions.append("开启手续费模拟，默认可使用 0.0003。")
    if not slippage_included:
        warnings.append("未计入滑点，短线策略收益可能被高估。")
        repair_suggestions.append("开启滑点模拟，默认可使用 0.001。")
    if not st_suspension_delist_handled:
        warnings.append("股票池可能存在幸存者偏差。")
    if not financial_announcement_lag_handled:
        warnings.append("财务因子可能存在前视偏差。")

    if is_sample_pool:
        level = "仅功能验证"
        sample_size_level = "样本充足" if trade_count >= 30 else "样本不足"
    elif data_coverage_ratio < 0.8:
        level = "数据不足"
        sample_size_level = "样本充足" if trade_count >= 30 else "样本不足"
    elif trade_count < 30:
        level = "样本不足"
        sample_size_level = "样本不足"
    elif backtest_days < 250:
        level = "区间不足"
        sample_size_level = "样本充足"
    elif warnings:
        level = "需谨慎"
        sample_size_level = "样本充足"
    else:
        level = "可信"
        sample_size_level = "样本充足"
    usable = level == "可信"
    return {
        "validityLevel": level,
        "validityWarnings": warnings,
        "repairSuggestions": list(dict.fromkeys(repair_suggestions)),
        "backtestDays": backtest_days,
        "stockPool": stock_pool,
        "stockPoolSize": stock_count,
        "dataCoverageRatio": round(data_coverage_ratio, 4),
        "feeIncluded": fee_included,
        "slippageIncluded": slippage_included,
        "stSuspensionDelistHandled": st_suspension_delist_handled,
        "survivorBiasRisk": survivor_bias_risk,
        "forwardBiasRisk": forward_bias_risk,
        "sampleSizeLevel": sample_size_level,
        "usableForDecision": usable,
        "usableForStrategyJudgement": usable,
        "metricsMuted": level != "可信",
        "conclusion": "本次回测仅用于功能验证，不作为策略有效性依据。" if not usable else "本次回测可作为策略研究参考，仍需人工确认。",
    }


def _run_classic_quant_backtest(strategy: dict, payload: dict[str, Any]) -> dict:
    strategy_id = int(strategy["id"])
    start_date = payload.get("start_date") or _default_start_date()
    end_date = payload.get("end_date") or _default_end_date()
    initial_cash = float(payload.get("initial_cash", 100000))
    fee_rate = float(payload.get("fee_rate", 0.0003))
    slippage = float(payload.get("slippage", 0.0005) or 0.0005)
    position_cap = min(float(payload.get("position_cap", 0.1) or 0.1), 0.1)
    max_positions = int(payload.get("max_positions", 8) or 8)
    stock_pool = payload.get("stock_pool", "all")
    codes = _resolve_stock_pool(stock_pool, strategy_id)
    stocks = _stocks_for_backtest(codes)
    frames = {stock["code"]: enrich_prices(get_prices(stock["code"], start_date=start_date, end_date=end_date)) for stock in stocks}
    stock_frames = [{"stock": stock, "frame": frames[stock["code"]]} for stock in stocks if not frames[stock["code"]].empty]
    daily_candidates: dict[str, list[dict]] = defaultdict(list)
    market_context_by_date: dict[str, dict[str, Any]] = {}

    for stock in stocks:
        frame = frames[stock["code"]]
        if frame.empty or len(frame) < 125:
            continue
        for idx in range(120, len(frame) - 1):
            trade_date = frame.iloc[idx]["date"].date().isoformat()
            context = market_context_by_date.get(trade_date)
            if context is None:
                context = market_regime_model(stock_frames, trade_date)
                market_context_by_date[trade_date] = context
            if payload.get("market_regime_filter") and context["marketRegime"] != payload.get("market_regime_filter"):
                continue
            signal = evaluate_classic_strategy(strategy, stock, frame, context, row_index=idx)
            if not signal:
                continue
            meta = signal.get("metadata", {}).get("strategyCandidate", {})
            if signal["risk_level"] == "high" or meta.get("suggestedAction") == "暂不参与":
                continue
            next_row = frame.iloc[idx + 1]
            one_day_return = safe_float(next_row["close"] / frame.iloc[idx]["close"] - 1) - fee_rate - slippage
            daily_candidates[next_row["date"].date().isoformat()].append(
                {
                    "date": next_row["date"].date().isoformat(),
                    "stock_code": stock["code"],
                    "score": float(signal["score"]),
                    "return": one_day_return,
                    "reason": signal["reason"],
                    "risk_level": signal["risk_level"],
                    "market_regime": context["marketRegime"],
                    "industry": stock.get("industry") or "未分类",
                }
            )

    cash = initial_cash
    equity_curve: list[dict] = []
    daily_returns: list[float] = []
    trades: list[dict] = []
    for trade_date in sorted(daily_candidates):
        picks = sorted(daily_candidates[trade_date], key=lambda item: item["score"], reverse=True)[:max_positions]
        weight = min(position_cap, 1 / len(picks)) if picks else 0
        portfolio_return = sum(weight * pick["return"] for pick in picks)
        cash *= 1 + portfolio_return
        daily_returns.append(portfolio_return)
        equity_curve.append({"date": trade_date, "value": round(cash, 2), "return": round(portfolio_return, 5)})
        for pick in picks:
            trades.append(
                {
                    "date": trade_date,
                    "stock_code": pick["stock_code"],
                    "action": "模拟观察",
                    "score": round(pick["score"], 2),
                    "return": round(pick["return"], 4),
                    "weight": round(weight, 4),
                    "reason": pick["reason"],
                    "risk_level": pick["risk_level"],
                    "market_regime": pick["market_regime"],
                    "industry": pick["industry"],
                    "holding_days": 1,
                }
            )

    if not equity_curve:
        equity_curve = [{"date": end_date, "value": initial_cash, "return": 0}]
        daily_returns = [0.0]

    drawdown_values = equity_drawdown([point["value"] for point in equity_curve])
    drawdown_curve = [{"date": point["date"], "value": round(drawdown, 5)} for point, drawdown in zip(equity_curve, drawdown_values, strict=False)]
    final_value = equity_curve[-1]["value"]
    total_return = final_value / initial_cash - 1
    periods = max(1, len(equity_curve))
    annual_return = (final_value / initial_cash) ** (252 / periods) - 1 if final_value > 0 else -1
    max_drawdown = abs(min(drawdown_values)) if drawdown_values else 0
    mean_return = float(np.mean(daily_returns))
    std_return = float(np.std(daily_returns))
    sharpe = (mean_return / std_return * math.sqrt(252)) if std_return > 0 else 0
    win_rate = len([trade for trade in trades if trade["return"] > 0]) / len(trades) if trades else 0
    turnover = min(1, len(trades) * position_cap / max(len(equity_curve), 1))
    calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
    result_json = {
        "stock_pool": stock_pool,
        "stock_count": len(codes),
        "initial_cash": initial_cash,
        "fee_rate": fee_rate,
        "slippage": slippage,
        "position_cap": position_cap,
        "max_positions": max_positions,
        "turnover": round(turnover, 4),
        "calmar": round(calmar, 4),
        "profit_loss_ratio": 0,
        "avg_holding_days": 1,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "regime_performance": _group_performance(trades, "market_regime"),
        "industry_performance": _group_performance(trades, "industry"),
        "year_performance": _group_performance([{**trade, "year": trade["date"][:4]} for trade in trades], "year"),
        "trades": trades,
    }
    timestamp = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO backtest_results
                (strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                 sharpe, win_rate, trade_count, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                start_date,
                end_date,
                round(total_return, 6),
                round(annual_return, 6),
                round(max_drawdown, 6),
                round(sharpe, 6),
                round(win_rate, 6),
                len(trades),
                json.dumps(result_json, ensure_ascii=False),
                timestamp,
            ),
        )
    return get_backtest_result(cursor.lastrowid) or {}


def _run_dragon_backtest(strategy: dict, payload: dict[str, Any]) -> dict:
    strategy_id = int(strategy["id"])
    start_date = payload.get("start_date") or _default_start_date()
    end_date = payload.get("end_date") or _default_end_date()
    initial_cash = float(payload.get("initial_cash", 100000))
    fee_rate = float(payload.get("fee_rate", 0.0003))
    stop_loss = abs(float(payload.get("stop_loss", 0.06) or 0.06))
    take_profit = float(payload.get("take_profit", 0.12) or 0.12)
    position_cap = min(float(payload.get("position_cap", 0.1) or 0.1), 0.1)
    max_positions = int(payload.get("max_positions", 3) or 3)
    max_holding_days = int(payload.get("max_holding_days", 5) or 5)
    stock_pool = payload.get("stock_pool", "all")
    stocks = _stocks_for_backtest(_resolve_stock_pool(stock_pool, strategy_id))
    frames = {
        stock["code"]: enrich_prices(get_prices(stock["code"], start_date=start_date, end_date=end_date))
        for stock in stocks
    }
    stock_frames = [{"stock": stock, "frame": frames[stock["code"]]} for stock in stocks if not frames[stock["code"]].empty]
    candidate_trades: dict[str, list[dict]] = defaultdict(list)
    observations: list[dict] = []
    unfiltered_returns: list[float] = []

    for stock in stocks:
        frame = frames[stock["code"]]
        if frame.empty or len(frame) < 65:
            continue
        for idx in range(60, len(frame) - 1):
            trade_date = frame.iloc[idx]["date"].date().isoformat()
            context = prepare_dragon_context(stock_frames, trade_date)
            signal, _diagnostics = evaluate_dragon_leader(strategy, stock, frame, context, row_index=idx)
            if not signal:
                continue
            meta = signal.get("metadata", {})
            observation = {
                "date": trade_date,
                "stock_code": stock["code"],
                "score": meta.get("dragonScore", signal["score"]),
                "risk_level": signal["risk_level"],
                "suggested_action": meta.get("suggestedAction"),
                "candidate_level": meta.get("candidateLevel"),
                "market_sentiment": meta.get("marketSentiment"),
                "board_height": meta.get("consecutiveLimitUpDays", 0),
            }
            observations.append(observation)
            simulated = _simulate_dragon_trade(frame, idx + 1, stop_loss, take_profit, max_holding_days, stock_frames, strategy)
            unfiltered_returns.append(simulated["return"])
            if signal["risk_level"] == "high" or meta.get("suggestedAction") == "暂不参与":
                continue
            entry_date = simulated["date"]
            candidate_trades[entry_date].append(
                {
                    **simulated,
                    "stock_code": stock["code"],
                    "score": float(meta.get("dragonScore", signal["score"])),
                    "reason": "；".join(meta.get("triggerReasons", [])) or signal["reason"],
                    "risk_level": signal["risk_level"],
                    "market_sentiment": meta.get("marketSentiment", "Cold"),
                    "board_height": int(meta.get("consecutiveLimitUpDays", 0) or 0),
                    "candidate_level": meta.get("candidateLevel", "观察候选"),
                }
            )

    cash = initial_cash
    equity_curve: list[dict] = []
    daily_returns: list[float] = []
    trades: list[dict] = []
    for trade_date in sorted(candidate_trades):
        picks = sorted(candidate_trades[trade_date], key=lambda item: item["score"], reverse=True)[:max_positions]
        if not picks:
            continue
        weight = min(position_cap, 1 / len(picks))
        portfolio_return = sum(weight * pick["return"] for pick in picks) - fee_rate * weight * len(picks)
        cash *= 1 + portfolio_return
        daily_returns.append(portfolio_return)
        equity_curve.append({"date": trade_date, "value": round(cash, 2), "return": round(portfolio_return, 5)})
        for pick in picks:
            trades.append(
                {
                    "date": trade_date,
                    "stock_code": pick["stock_code"],
                    "action": "模拟观察",
                    "score": round(pick["score"], 2),
                    "return": round(pick["return"], 4),
                    "weight": round(weight, 4),
                    "reason": pick["reason"],
                    "risk_level": pick["risk_level"],
                    "holding_days": pick["holding_days"],
                    "exit_reason": pick["exit_reason"],
                    "market_sentiment": pick["market_sentiment"],
                    "board_height": pick["board_height"],
                }
            )

    if not equity_curve:
        equity_curve = [{"date": end_date, "value": initial_cash, "return": 0}]
        daily_returns = [0.0]

    drawdown_values = equity_drawdown([point["value"] for point in equity_curve])
    drawdown_curve = [
        {"date": point["date"], "value": round(drawdown, 5)}
        for point, drawdown in zip(equity_curve, drawdown_values, strict=False)
    ]
    final_value = equity_curve[-1]["value"]
    total_return = final_value / initial_cash - 1
    periods = max(1, len(equity_curve))
    annual_return = (final_value / initial_cash) ** (252 / periods) - 1 if final_value > 0 else -1
    max_drawdown = abs(min(drawdown_values)) if drawdown_values else 0
    mean_return = float(np.mean(daily_returns))
    std_return = float(np.std(daily_returns))
    sharpe = (mean_return / std_return * math.sqrt(252)) if std_return > 0 else 0
    winning_returns = [item["return"] for item in trades if item["return"] > 0]
    losing_returns = [abs(item["return"]) for item in trades if item["return"] < 0]
    win_rate = len(winning_returns) / len(trades) if trades else 0
    profit_loss_ratio = (sum(winning_returns) / len(winning_returns)) / (sum(losing_returns) / len(losing_returns)) if winning_returns and losing_returns else 0
    avg_holding_days = sum(float(item.get("holding_days", 0)) for item in trades) / len(trades) if trades else 0
    max_single_loss = min((item["return"] for item in trades), default=0)

    result_json = {
        "stock_pool": stock_pool,
        "stock_count": len(stocks),
        "initial_cash": initial_cash,
        "fee_rate": fee_rate,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "position_cap": position_cap,
        "max_positions": max_positions,
        "max_holding_days": max_holding_days,
        "profit_loss_ratio": round(profit_loss_ratio, 4),
        "avg_holding_days": round(avg_holding_days, 2),
        "max_single_loss": round(max_single_loss, 4),
        "sentiment_performance": _group_performance(trades, "market_sentiment"),
        "board_height_performance": _group_performance(trades, "board_height"),
        "high_risk_filter_comparison": {
            "after_filter_avg_return": round(sum(item["return"] for item in trades) / len(trades), 4) if trades else 0,
            "before_filter_avg_return": round(sum(unfiltered_returns) / len(unfiltered_returns), 4) if unfiltered_returns else 0,
            "high_risk_observation_count": len([item for item in observations if item["risk_level"] == "high"]),
        },
        "observations": observations[:300],
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trades": trades,
    }
    timestamp = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO backtest_results
                (strategy_id, start_date, end_date, total_return, annual_return, max_drawdown,
                 sharpe, win_rate, trade_count, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                start_date,
                end_date,
                round(total_return, 6),
                round(annual_return, 6),
                round(max_drawdown, 6),
                round(sharpe, 6),
                round(win_rate, 6),
                len(trades),
                json.dumps(result_json, ensure_ascii=False),
                timestamp,
            ),
        )
    return get_backtest_result(cursor.lastrowid) or {}


def _simulate_dragon_trade(
    frame: Any,
    entry_idx: int,
    stop_loss: float,
    take_profit: float,
    max_holding_days: int,
    stock_frames: list[dict],
    strategy: dict,
) -> dict:
    entry = frame.iloc[entry_idx]
    entry_price = safe_float(entry.get("open")) or safe_float(entry.get("close"))
    exit_idx = min(entry_idx + max_holding_days - 1, len(frame) - 1)
    exit_reason = "达到最大观察周期"
    for idx in range(entry_idx, min(entry_idx + max_holding_days, len(frame))):
        row = frame.iloc[idx]
        close = safe_float(row.get("close"))
        trade_date = row["date"].date().isoformat()
        current_return = close / entry_price - 1 if entry_price else 0
        context = prepare_dragon_context(stock_frames, trade_date)
        if current_return <= -stop_loss:
            exit_idx = idx
            exit_reason = "触发 -6% 风险控制线"
            break
        if current_return >= take_profit:
            exit_idx = idx
            exit_reason = "达到 +12% 阶段收益观察目标"
            break
        if close < safe_float(row.get("ma5")):
            exit_idx = idx
            exit_reason = "跌破 5 日均线，退出观察"
            break
        if context.get("marketSentiment") == "Cold":
            exit_idx = idx
            exit_reason = "市场情绪转为 Cold，退出观察"
            break
    exit_row = frame.iloc[exit_idx]
    exit_price = safe_float(exit_row.get("close")) or entry_price
    trade_return = exit_price / entry_price - 1 if entry_price else 0
    return {
        "date": entry["date"].date().isoformat(),
        "entry_price": round(entry_price, 2),
        "exit_date": exit_row["date"].date().isoformat(),
        "exit_price": round(exit_price, 2),
        "return": trade_return,
        "holding_days": exit_idx - entry_idx + 1,
        "exit_reason": exit_reason,
    }


def _stocks_for_backtest(codes: list[str]) -> list[dict]:
    if not codes:
        return []
    placeholders = ",".join("?" for _ in codes)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT code, name, industry, market, list_date, is_st, is_suspended, float_market_cap
            FROM stocks
            WHERE code IN ({placeholders})
            ORDER BY code
            """,
            codes,
        ).fetchall()
    return dicts_from_rows(rows)


def _group_performance(trades: list[dict], key: str) -> dict[str, dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(key, "未知"))].append(float(trade.get("return", 0)))
    return {
        name: {
            "count": len(values),
            "avg_return": round(sum(values) / len(values), 4) if values else 0,
            "win_rate": round(len([value for value in values if value > 0]) / len(values), 4) if values else 0,
        }
        for name, values in grouped.items()
    }


def _summarize_result_json(result_json: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_pool": result_json.get("stock_pool", ""),
        "stock_count": result_json.get("stock_count", 0),
        "initial_cash": result_json.get("initial_cash", 0),
        "fee_rate": result_json.get("fee_rate", 0),
        "slippage": result_json.get("slippage", 0),
        "data_coverage_ratio": result_json.get("data_coverage_ratio", 1),
        "st_suspension_delist_handled": result_json.get("st_suspension_delist_handled", False),
        "financial_announcement_lag_handled": result_json.get("financial_announcement_lag_handled", False),
        "stop_loss": result_json.get("stop_loss", 0),
        "take_profit": result_json.get("take_profit"),
        "position_cap": result_json.get("position_cap", 0),
        "max_positions": result_json.get("max_positions"),
        "max_holding_days": result_json.get("max_holding_days"),
        "profit_loss_ratio": result_json.get("profit_loss_ratio", 0),
        "avg_holding_days": result_json.get("avg_holding_days"),
        "max_single_loss": result_json.get("max_single_loss"),
        "equity_curve": [],
        "drawdown_curve": [],
        "trades": [],
    }


def _resolve_stock_pool(stock_pool: str, strategy_id: int) -> list[str]:
    if stock_pool in {"all_market"}:
        stock_pool = "all"
    if stock_pool in {"current_candidates"}:
        stock_pool = "today_candidates"
    with get_connection() as conn:
        if stock_pool == "sample":
            rows = conn.execute(
                """
                SELECT code
                FROM stocks
                WHERE code IN (SELECT DISTINCT stock_code FROM daily_prices)
                ORDER BY code
                LIMIT 12
                """
            ).fetchall()
            return [row["code"] for row in rows]
        if stock_pool in {"main_watchlist", "hotspot_watchlist", "manual_watchlist"}:
            latest = conn.execute("SELECT MAX(date) AS d FROM signals").fetchone()["d"]
            if not latest:
                return []
            if stock_pool == "manual_watchlist":
                return []
            pattern = "%main_observation%" if stock_pool == "main_watchlist" else "%热点%"
            rows = conn.execute(
                """
                SELECT DISTINCT stock_code
                FROM signals
                WHERE date = ? AND (metadata LIKE ? OR strategy_name LIKE ?)
                ORDER BY stock_code
                """,
                (latest, pattern, pattern),
            ).fetchall()
            return [row["stock_code"] for row in rows]
        if stock_pool in {"today_candidates", "today_candidates_only"}:
            latest = conn.execute("SELECT MAX(date) AS d FROM signals").fetchone()["d"]
            if latest:
                rows = conn.execute(
                    "SELECT DISTINCT stock_code FROM signals WHERE date = ? AND strategy_id = ? ORDER BY stock_code",
                    (latest, strategy_id),
                ).fetchall()
                codes = [row["stock_code"] for row in rows]
                if codes:
                    return codes
            if stock_pool == "today_candidates_only":
                return []
        rows = conn.execute("SELECT code FROM stocks ORDER BY code").fetchall()
    return [row["code"] for row in rows]


def _market_volatility(codes: list[str]) -> float:
    values: list[float] = []
    for code in codes:
        enriched = enrich_prices(get_prices(code, limit=120))
        if not enriched.empty:
            values.append(safe_float(enriched.iloc[-1].get("volatility_60")))
    values = [value for value in values if value > 0]
    return sum(values) / len(values) if values else 0.03


def _default_start_date() -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT date FROM daily_prices ORDER BY date ASC LIMIT 1").fetchone()
    return row["date"] if row else datetime.now().date().isoformat()


def _default_end_date() -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT date FROM daily_prices ORDER BY date DESC LIMIT 1").fetchone()
    return row["date"] if row else datetime.now().date().isoformat()


def _trading_dates_until(end_date: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT date
            FROM daily_prices
            WHERE date <= ?
            ORDER BY date ASC
            """,
            (end_date,),
        ).fetchall()
    return [row["date"] for row in rows]


def _start_date_by_trading_days(trade_dates: list[str], lookback: int, end_date: str) -> str:
    if trade_dates:
        index = max(0, len(trade_dates) - lookback)
        return trade_dates[index]
    # TODO: 接入交易日历不可用时，目前使用自然日近似计算快捷周期。
    end = datetime.fromisoformat(end_date).date()
    return (end - timedelta(days=int(lookback / 5 * 7))).isoformat()


def _date_span_days(start_date: str | None, end_date: str | None) -> int:
    try:
        start = datetime.fromisoformat(str(start_date)).date()
        end = datetime.fromisoformat(str(end_date)).date()
        return max((end - start).days + 1, 0)
    except (TypeError, ValueError):
        return 0
