from __future__ import annotations

import json
import math
from statistics import mean, pstdev
from typing import Any, Callable

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services.backtest_service import check_backtest_validity

PERIODS = {
    "1M": 20,
    "3M": 60,
    "6M": 120,
    "1Y": 250,
    "ALL": None,
}
DEFAULT_PERIODS = ["1M", "3M", "6M", "1Y"]
DEFAULT_PARAMETER_HASH = "default"
DEFAULT_DATA_VERSION = "local-sqlite-v1"
DEFAULT_BENCHMARK_CODE = "LOCAL_EQUAL_WEIGHT"
ProgressCallback = Callable[[int, str], None]


def refresh_strategy_performance(force: bool = False, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    timestamp = now_iso()
    strategies = _list_strategies()
    latest_backtests = _latest_backtests_by_strategy()
    total = max(len(strategies), 1)
    success_count = 0
    failed: list[dict[str, str]] = []
    periods_written = 0

    for index, strategy in enumerate(strategies, start=1):
        strategy_name = strategy["name"]
        if progress_callback:
            progress_callback(5 + int(index / total * 80), f"正在刷新策略收益 {index}/{len(strategies)}：{strategy_name}")
        backtest = latest_backtests.get(strategy_name)
        try:
            if not backtest:
                _write_empty_summaries(strategy_name, timestamp)
                success_count += 1
                periods_written += len(DEFAULT_PERIODS)
                continue
            if force or not _has_current_summary(strategy_name, backtest["end_date"]):
                generate_strategy_nav_daily(strategy_name, backtest, timestamp=timestamp)
                _persist_trade_records(strategy_name, backtest, timestamp=timestamp)
                for period in DEFAULT_PERIODS:
                    performance = calculate_strategy_period_performance(strategy_name, period)
                    _upsert_summary(performance, timestamp)
                    periods_written += 1
            success_count += 1
        except Exception as exc:  # noqa: BLE001 - performance refresh should keep other strategies running
            failed.append({"strategyName": strategy_name, "reason": str(exc)[:200]})

    if progress_callback:
        progress_callback(95, "策略收益预聚合已完成")
    return {
        "strategyCount": len(strategies),
        "successCount": success_count,
        "failedCount": len(failed),
        "periodsWritten": periods_written,
        "failed": failed,
        "updatedAt": timestamp,
    }


def generate_strategy_nav_from_backtests(
    strategy_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    force: bool = False,
    progress_callback: ProgressCallback | None = None,
    source_task_id: int | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    strategies = _list_strategies()
    if strategy_name:
        strategies = [strategy for strategy in strategies if strategy["name"] == strategy_name]
    latest_backtests = _latest_backtests_by_strategy()
    total = max(len(strategies), 1)
    nav_count = 0
    trade_count = 0
    summary_count = 0
    failed: list[dict[str, str]] = []
    missing: list[str] = []

    for index, strategy in enumerate(strategies, start=1):
        name = strategy["name"]
        if progress_callback:
            progress_callback(5 + int(index / total * 85), f"正在生成策略每日净值 {index}/{len(strategies)}：{name}")
        try:
            backtest = latest_backtests.get(name)
            if force or not backtest:
                from app.services.backtest_service import run_backtest  # Local import avoids a module cycle.

                payload = {
                    "strategy_id": strategy["id"],
                    "start_date": start_date,
                    "end_date": end_date,
                    "stock_pool": "today_candidates_only",
                }
                backtest = run_backtest({key: value for key, value in payload.items() if value})
                latest_backtests[name] = backtest
            if not backtest:
                missing.append(name)
                continue
            nav_count += generate_strategy_nav_daily(name, backtest, timestamp=timestamp, source_task_id=source_task_id)
            trade_count += _persist_trade_records(name, backtest, timestamp=timestamp, source_task_id=source_task_id)
            for period in DEFAULT_PERIODS:
                performance = calculate_strategy_period_performance(name, period)
                _upsert_summary(performance, timestamp)
                summary_count += 1
        except Exception as exc:  # noqa: BLE001 - keep other strategies repairable
            failed.append({"strategyName": name, "reason": str(exc)[:200]})

    return {
        "strategyCount": len(strategies),
        "navGeneratedCount": nav_count,
        "tradeRecordCount": trade_count,
        "summaryRefreshedCount": summary_count,
        "missingNavStrategies": missing,
        "failedStrategies": failed,
        "failedCount": len(failed),
        "updatedAt": timestamp,
    }


def refresh_strategy_performance_summary(
    strategy_name: str | None = None,
    end_date: str | None = None,
    force: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    strategies = _list_strategies()
    if strategy_name:
        strategies = [strategy for strategy in strategies if strategy["name"] == strategy_name]
    total = max(len(strategies), 1)
    refreshed = 0
    failed: list[dict[str, str]] = []
    for index, strategy in enumerate(strategies, start=1):
        name = strategy["name"]
        if progress_callback:
            progress_callback(10 + int(index / total * 80), f"正在刷新收益汇总 {index}/{len(strategies)}：{name}")
        try:
            latest_nav_date = _latest_nav_date(name)
            if not latest_nav_date:
                for period in DEFAULT_PERIODS:
                    _upsert_summary(_empty_performance(name, period), timestamp)
                    refreshed += 1
                continue
            if end_date and latest_nav_date < end_date and not force:
                failed.append({"strategyName": name, "reason": f"最新净值日期 {latest_nav_date} 早于目标日期 {end_date}"})
                continue
            for period in DEFAULT_PERIODS:
                performance = calculate_strategy_period_performance(name, period)
                _upsert_summary(performance, timestamp)
                refreshed += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"strategyName": name, "reason": str(exc)[:200]})
    return {
        "strategyCount": len(strategies),
        "summaryRefreshedCount": refreshed,
        "failedCount": len(failed),
        "failedStrategies": failed,
        "updatedAt": timestamp,
    }


def validate_strategy_performance_data() -> dict[str, Any]:
    strategies = _list_strategies()
    latest_trade_date = _latest_market_date()
    missing_nav: list[str] = []
    missing_summary: list[str] = []
    stale_summary: list[str] = []
    insufficient_sample: list[str] = []
    low_coverage: set[str] = set()
    period_coverage_diagnostics: list[dict[str, Any]] = []
    invalid_zero_return: list[str] = []
    warnings: list[str] = []

    for strategy in strategies:
        name = strategy["name"]
        nav_stats = _nav_stats(name)
        nav_count = int(nav_stats["nav_count"] or 0)
        if nav_count == 0:
            missing_nav.append(name)
        for period in DEFAULT_PERIODS:
            required_rows = PERIODS[period] or nav_count
            available_rows = min(nav_count, required_rows) if required_rows else nav_count
            coverage_ratio = available_rows / max(required_rows, 1) if required_rows else 1.0
            period_coverage_diagnostics.append(
                {
                    "strategyName": name,
                    "period": period,
                    "requiredRows": required_rows,
                    "availableRows": available_rows,
                    "missingRows": max(0, required_rows - available_rows),
                    "coverageRatio": round(coverage_ratio, 6),
                    "earliestNavDate": nav_stats.get("earliest_date"),
                    "latestNavDate": nav_stats.get("latest_date"),
                }
            )
            if coverage_ratio < 0.8:
                low_coverage.add(f"{name}:{period}")
        periods = {row["period"]: row for row in _summary_rows_for_strategy(name)}
        if any(period not in periods for period in DEFAULT_PERIODS):
            missing_summary.append(name)
        for period, row in periods.items():
            if latest_trade_date and row.get("end_date") and row["end_date"] < latest_trade_date:
                stale_summary.append(f"{name}:{period}")
            if row.get("validity_level") == "样本不足":
                insufficient_sample.append(f"{name}:{period}")
            if float(row.get("data_coverage_ratio") or 0) < 0.8:
                low_coverage.add(f"{name}:{period}")
            if float(row.get("return_rate") or 0) == 0 and int(row.get("trade_count") or 0) == 0 and nav_count == 0:
                invalid_zero_return.append(f"{name}:{period}")

    if missing_nav:
        warnings.append("部分策略缺少 strategy_nav_daily，每日净值不足会导致走势图为空。")
    if missing_summary:
        warnings.append("部分策略缺少 1M/3M/6M/1Y 收益汇总。")
    if invalid_zero_return:
        warnings.append("发现零收益但缺少 NAV 的异常记录，已按数据异常处理。")
    return {
        "latestTradeDate": latest_trade_date,
        "missingNavStrategies": missing_nav,
        "missingSummaryStrategies": missing_summary,
        "staleSummaryItems": stale_summary,
        "insufficientSampleItems": insufficient_sample,
        "lowCoverageItems": sorted(low_coverage),
        "periodCoverageDiagnostics": period_coverage_diagnostics,
        "invalidZeroReturnItems": invalid_zero_return,
        "warnings": warnings,
        "isHealthy": not (missing_nav or missing_summary or invalid_zero_return),
    }


def generate_strategy_nav_daily(
    strategy_name: str,
    backtest: dict[str, Any],
    timestamp: str | None = None,
    benchmark_code: str = DEFAULT_BENCHMARK_CODE,
    parameter_hash: str = DEFAULT_PARAMETER_HASH,
    data_version: str = DEFAULT_DATA_VERSION,
    source_task_id: int | None = None,
) -> int:
    timestamp = timestamp or now_iso()
    result_json = _parse_json(backtest.get("result_json"), {})
    equity_curve = result_json.get("equity_curve") or []
    if not equity_curve:
        return 0
    initial_cash = float(result_json.get("initial_cash") or equity_curve[0].get("value") or 1)
    values_by_date = {str(point["date"]): float(point.get("value") or initial_cash) for point in equity_curve if point.get("date")}
    trade_dates = _trading_dates(backtest["start_date"], backtest["end_date"])
    if not trade_dates:
        trade_dates = sorted(values_by_date)

    rows: list[tuple] = []
    previous_nav = 1.0
    latest_value = initial_cash
    peak_nav = 1.0
    benchmark_nav = 1.0
    benchmark_returns = _benchmark_returns(backtest["start_date"], backtest["end_date"])
    for trade_date in trade_dates:
        latest_value = values_by_date.get(trade_date, latest_value)
        nav = latest_value / initial_cash if initial_cash else 1.0
        daily_return = nav / previous_nav - 1 if previous_nav else 0
        peak_nav = max(peak_nav, nav)
        drawdown = nav / peak_nav - 1 if peak_nav else 0
        benchmark_return = benchmark_returns.get(trade_date, 0.0)
        benchmark_nav *= 1 + benchmark_return
        rows.append(
            (
                trade_date,
                strategy_name,
                round(nav, 6),
                round(daily_return, 6),
                round(nav - 1, 6),
                benchmark_code,
                round(benchmark_nav, 6),
                round(benchmark_return, 6),
                round(drawdown, 6),
                None,
                data_version,
                parameter_hash,
                source_task_id,
                timestamp,
                timestamp,
            )
        )
        previous_nav = nav

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO strategy_nav_daily (
                trade_date, strategy_name, nav, daily_return, cumulative_return,
                benchmark_code, benchmark_nav, benchmark_return, drawdown, market_regime,
                data_version, parameter_hash, source_task_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, strategy_name) DO UPDATE SET
                nav = excluded.nav,
                daily_return = excluded.daily_return,
                cumulative_return = excluded.cumulative_return,
                benchmark_code = excluded.benchmark_code,
                benchmark_nav = excluded.benchmark_nav,
                benchmark_return = excluded.benchmark_return,
                drawdown = excluded.drawdown,
                market_regime = excluded.market_regime,
                data_version = excluded.data_version,
                parameter_hash = excluded.parameter_hash,
                source_task_id = excluded.source_task_id,
                updated_at = excluded.updated_at
            """,
            rows,
        )
    return len(rows)


def calculate_strategy_period_performance(strategy_name: str, period: str, benchmark_code: str | None = None) -> dict[str, Any]:
    period_key = period if period in PERIODS else "1M"
    nav_rows = _nav_rows(strategy_name)
    if not nav_rows:
        return _empty_performance(strategy_name, period_key)
    expected_days = PERIODS[period_key]
    rows = nav_rows if expected_days is None else nav_rows[-expected_days:]
    start = rows[0]
    end = rows[-1]
    start_nav = float(start["nav"] or 1)
    end_nav = float(end["nav"] or start_nav)
    returns = [float(row["daily_return"] or 0) for row in rows]
    nav_values = [float(row["nav"] or 1) for row in rows]
    benchmark_start = float(start["benchmark_nav"] or 1)
    benchmark_end = float(end["benchmark_nav"] or benchmark_start)
    return_rate = end_nav / start_nav - 1 if start_nav else 0
    max_drawdown = abs(_period_max_drawdown(nav_values))
    volatility = pstdev(returns) * math.sqrt(252) if len(returns) > 1 else 0
    sharpe = mean(returns) / pstdev(returns) * math.sqrt(252) if len(returns) > 1 and pstdev(returns) > 0 else 0
    annualized = (1 + return_rate) ** (252 / max(len(rows), 1)) - 1 if return_rate > -1 else -1
    trades = _trade_records(strategy_name, rows[0]["trade_date"], rows[-1]["trade_date"])
    trade_count = len(trades)
    win_rate = len([trade for trade in trades if float(trade.get("return_rate") or 0) > 0]) / trade_count if trade_count else 0
    avg_holding_days = sum(float(trade.get("holding_days") or 0) for trade in trades) / trade_count if trade_count else 0
    expected = len(nav_rows) if expected_days is None else expected_days
    data_coverage = min(1.0, len(rows) / max(expected, 1))
    benchmark_return = benchmark_end / benchmark_start - 1 if benchmark_start else 0
    warnings: list[str] = []
    latest_backtest = _latest_backtests_by_strategy().get(strategy_name)
    trade_detail_incomplete = False
    if latest_backtest:
        expected_trade_count = int(latest_backtest.get("trade_count") or 0)
        persisted_trade_count = _persisted_trade_count(strategy_name)
        raw_trade_count = len((_parse_json(latest_backtest.get("result_json"), {}) or {}).get("trades") or [])
        if expected_trade_count > max(persisted_trade_count, raw_trade_count):
            trade_detail_incomplete = True
            warnings.append("交易明细不完整，请重新回测以生成完整 strategy_trade_records。")
    if data_coverage < 0.8:
        validity = "数据不足"
        warnings.append("该周期策略净值覆盖率不足。")
    elif trade_detail_incomplete:
        validity = "数据不足"
    elif trade_count < 30:
        validity = "样本不足"
        warnings.append("交易次数不足 30，统计意义较弱。")
    else:
        validity = "可信"
    if latest_backtest:
        backtest_validity = check_backtest_validity(latest_backtest)
        for warning in backtest_validity.get("validityWarnings", []):
            if warning not in warnings:
                warnings.append(warning)
        if validity == "可信" and backtest_validity.get("validityLevel") != "可信":
            validity = "需谨慎"

    return {
        "strategyName": strategy_name,
        "period": period_key,
        "startDate": rows[0]["trade_date"],
        "endDate": rows[-1]["trade_date"],
        "startNav": round(start_nav, 6),
        "endNav": round(end_nav, 6),
        "returnRate": round(return_rate, 6),
        "annualizedReturn": round(annualized, 6),
        "maxDrawdown": round(max_drawdown, 6),
        "volatility": round(volatility, 6),
        "sharpeRatio": round(sharpe, 6),
        "winRate": round(win_rate, 6),
        "tradeCount": trade_count,
        "avgHoldingDays": round(avg_holding_days, 2),
        "benchmarkReturn": round(benchmark_return, 6),
        "excessReturn": round(return_rate - benchmark_return, 6),
        "dataCoverageRatio": round(data_coverage, 6),
        "validityLevel": validity,
        "warnings": warnings,
        "parameterHash": DEFAULT_PARAMETER_HASH,
        "dataVersion": DEFAULT_DATA_VERSION,
    }


def get_strategy_performance_summary(
    periods: list[str] | None = None,
    strategy_names: list[str] | None = None,
    benchmark_code: str | None = None,
) -> dict[str, Any]:
    requested_periods = [period for period in (periods or DEFAULT_PERIODS) if period in PERIODS] or DEFAULT_PERIODS
    if not _has_any_summary():
        refresh_strategy_performance(force=False)
    strategies = _list_strategies()
    if strategy_names:
        selected = set(strategy_names)
        strategies = [strategy for strategy in strategies if strategy["name"] in selected]
    summaries = _summary_rows(requested_periods)
    by_strategy_period = {(row["strategy_name"], row["period"]): row for row in summaries}
    latest_backtests = _latest_backtests_by_strategy()
    rows: list[dict[str, Any]] = []
    for strategy in strategies:
        periods_map = {}
        for period in requested_periods:
            row = by_strategy_period.get((strategy["name"], period))
            periods_map[period] = _period_from_summary_row(strategy["name"], period, row)
        diagnosis = diagnose_strategy_performance(strategy["name"], periods_map)
        latest_backtest = latest_backtests.get(strategy["name"])
        validity = check_backtest_validity(latest_backtest)["validityLevel"] if latest_backtest else "数据不足"
        rows.append(
            {
                "strategyName": strategy["name"],
                "strategyType": strategy["type"],
                "enabled": bool(strategy["enabled"]),
                "todayStatus": diagnosis["suggestedStrategyAction"] if strategy["enabled"] else "暂停",
                "periods": periods_map,
                "latestBacktestValidity": validity,
                "performanceStatus": diagnosis["performanceStatus"],
                "diagnosisText": diagnosis["diagnosisText"],
                "suggestedStrategyAction": diagnosis["suggestedStrategyAction"] if strategy["enabled"] else "暂停",
            }
        )
    overview = _performance_overview(rows)
    return {
        "periods": requested_periods,
        "benchmarkCode": benchmark_code or "LOCAL_EQUAL_WEIGHT",
        "updatedAt": max([row.get("periods", {}).get("1M", {}).get("updatedAt", "") for row in rows] or [""]),
        "overview": overview,
        "validation": validate_strategy_performance_data(),
        "strategies": rows,
    }


def get_strategy_nav(strategy_names: list[str] | None = None, period: str = "1Y", benchmark_code: str | None = None) -> dict[str, Any]:
    period_key = period if period in PERIODS else "1Y"
    names = strategy_names or [strategy["name"] for strategy in _list_strategies()[:5]]
    expected = PERIODS[period_key]
    series = []
    for name in names[:8]:
        rows = _nav_rows(name)
        if expected is not None:
            rows = rows[-expected:]
        series.append(
            {
                "strategyName": name,
                "points": [
                    {
                        "tradeDate": row["trade_date"],
                        "nav": row["nav"],
                        "dailyReturn": row["daily_return"],
                        "cumulativeReturn": row["cumulative_return"],
                        "drawdown": row["drawdown"],
                        "benchmarkNav": row["benchmark_nav"],
                        "benchmarkReturn": row["benchmark_return"],
                    }
                    for row in rows
                ],
            }
        )
    return {"period": period_key, "benchmarkCode": benchmark_code or "LOCAL_EQUAL_WEIGHT", "series": series}


def get_strategy_performance_detail(strategy_name: str, period: str = "1Y") -> dict[str, Any]:
    periods_map = {period_key: calculate_strategy_period_performance(strategy_name, period_key) for period_key in DEFAULT_PERIODS}
    nav = get_strategy_nav([strategy_name], period=period)
    rows = nav["series"][0]["points"] if nav["series"] else []
    trades = _trade_records(strategy_name, rows[0]["tradeDate"], rows[-1]["tradeDate"]) if rows else []
    diagnosis = diagnose_strategy_performance(strategy_name, periods_map)
    return {
        "strategyName": strategy_name,
        "periods": periods_map,
        "nav": rows,
        "drawdown": [{"tradeDate": row["tradeDate"], "drawdown": row["drawdown"]} for row in rows],
        "dailyReturns": [{"tradeDate": row["tradeDate"], "dailyReturn": row["dailyReturn"]} for row in rows],
        "trades": trades[:80],
        "diagnosis": diagnosis,
    }


def get_dashboard_strategy_performance() -> dict[str, Any]:
    summary = get_strategy_performance_summary(DEFAULT_PERIODS)
    rows = summary.get("strategies", [])
    from app.services.strategy_source_service import list_strategy_sources

    source_by_name = {source["strategyName"]: source for source in list_strategy_sources()}

    def valid_period(row: dict[str, Any], period: str) -> bool:
        data = row.get("periods", {}).get(period, {})
        return data.get("returnRate") is not None and data.get("validityLevel") not in {"样本不足", "数据不足"}

    def brief(row: dict[str, Any], period: str = "1Y") -> dict[str, Any]:
        period_data = row.get("periods", {}).get(period, {})
        one_year = row.get("periods", {}).get("1Y", {})
        source = source_by_name.get(row["strategyName"], {})
        return {
            "strategyName": row["strategyName"],
            "strategyType": row.get("strategyType"),
            "period": period,
            "returnRate": period_data.get("returnRate"),
            "maxDrawdown": one_year.get("maxDrawdown"),
            "validityLevel": period_data.get("validityLevel") or row.get("latestBacktestValidity"),
            "strategyStatus": row.get("suggestedStrategyAction") or row.get("todayStatus"),
            "sourceName": source.get("sourceName"),
            "sourceType": source.get("sourceType"),
            "sourceConfidence": source.get("confidenceLevel"),
            "backtestValidity": source.get("backtestValidity") or row.get("latestBacktestValidity"),
        }

    valid_1m = [row for row in rows if valid_period(row, "1M")]
    valid_3m = [row for row in rows if valid_period(row, "3M")]
    best_1m = max(valid_1m, key=lambda row: row["periods"]["1M"]["returnRate"]) if valid_1m else None
    best_3m = max(valid_3m, key=lambda row: row["periods"]["3M"]["returnRate"]) if valid_3m else None
    drawdown_rows = [
        row for row in rows if row.get("periods", {}).get("1Y", {}).get("maxDrawdown") is not None
    ]
    worst_drawdown = max(drawdown_rows, key=lambda row: row["periods"]["1Y"]["maxDrawdown"]) if drawdown_rows else None

    recommended_rows = sorted(
        valid_3m,
        key=lambda row: (
            bool(row.get("enabled")),
            row["periods"]["3M"].get("returnRate") or -999,
            -(row["periods"].get("1Y", {}).get("maxDrawdown") or 0),
        ),
        reverse=True,
    )[:5]
    if not recommended_rows:
        recommended_rows = sorted(rows, key=lambda row: bool(row.get("enabled")), reverse=True)[:5]
    nav_names = [row["strategyName"] for row in recommended_rows[:5]]
    nav = get_strategy_nav(nav_names, period="1Y") if nav_names else {"series": []}

    period_returns = []
    heatmap = []
    for row in rows:
        source = source_by_name.get(row["strategyName"], {})
        periods = row.get("periods", {})
        one_year = periods.get("1Y", {})
        period_returns.append(
            {
                "strategyName": row["strategyName"],
                "strategyType": row.get("strategyType"),
                "return1M": periods.get("1M", {}).get("returnRate"),
                "return3M": periods.get("3M", {}).get("returnRate"),
                "return6M": periods.get("6M", {}).get("returnRate"),
                "return1Y": one_year.get("returnRate"),
                "maxDrawdown1Y": one_year.get("maxDrawdown"),
                "winRate1Y": one_year.get("winRate"),
                "tradeCount1Y": one_year.get("tradeCount"),
                "sharpe1Y": one_year.get("sharpeRatio"),
                "validityLevel": one_year.get("validityLevel") or row.get("latestBacktestValidity"),
                "sourceName": source.get("sourceName"),
                "sourceConfidence": source.get("confidenceLevel"),
                "suggestedStrategyAction": row.get("suggestedStrategyAction"),
            }
        )
        for period in DEFAULT_PERIODS:
            period_data = periods.get(period, {})
            heatmap.append(
                {
                    "strategyName": row["strategyName"],
                    "period": period,
                    "returnRate": period_data.get("returnRate"),
                    "validityLevel": period_data.get("validityLevel", "数据不足"),
                }
            )

    warnings = list(summary.get("validation", {}).get("warnings", []))
    if not any(series.get("points") for series in nav.get("series", [])):
        warnings.append("暂无策略净值数据，请先运行回测或生成策略每日净值。")

    return {
        "updatedAt": summary.get("updatedAt") or now_iso(),
        "periods": DEFAULT_PERIODS,
        "best1M": brief(best_1m, "1M") if best_1m else None,
        "best3M": brief(best_3m, "3M") if best_3m else None,
        "worstDrawdown": brief(worst_drawdown, "1Y") if worst_drawdown else None,
        "recommendedStrategies": [brief(row, "3M") for row in recommended_rows],
        "navSeries": [
            {
                "strategyName": series["strategyName"],
                "points": [
                    {
                        "date": point["tradeDate"],
                        "nav": point["nav"],
                        "cumulativeReturn": point["cumulativeReturn"],
                        "drawdown": point["drawdown"],
                    }
                    for point in series.get("points", [])
                ],
            }
            for series in nav.get("series", [])
        ],
        "periodReturns": period_returns,
        "heatmap": heatmap,
        "warnings": warnings,
    }


def diagnose_strategy_performance(strategy_name: str, periods_map: dict[str, dict]) -> dict[str, str]:
    one_month = periods_map.get("1M", {})
    three_month = periods_map.get("3M", {})
    six_month = periods_map.get("6M", {})
    one_year = periods_map.get("1Y", {})
    one_year_trades = int(one_year.get("tradeCount") or 0)
    if one_year.get("validityLevel") in {"样本不足", "数据不足"} or one_year_trades < 30:
        return {
            "performanceStatus": "样本不足",
            "diagnosisText": f"{strategy_name} 近 1 年交易次数不足 30，不宜仅凭收益率判断策略有效性。",
            "suggestedStrategyAction": "仅复盘",
        }
    if (three_month.get("returnRate") or 0) < 0 and (three_month.get("excessReturn") or 0) < 0:
        return {
            "performanceStatus": "偏弱",
            "diagnosisText": f"{strategy_name} 近 3 月表现偏弱且跑输基准，需降低策略权重或进入复盘。",
            "suggestedStrategyAction": "降权观察",
        }
    if (six_month.get("maxDrawdown") or 0) > 0.2:
        return {
            "performanceStatus": "一般",
            "diagnosisText": f"{strategy_name} 近半年最大回撤超过 20%，需检查风控条件。",
            "suggestedStrategyAction": "降权观察",
        }
    if (one_month.get("returnRate") or 0) > (one_month.get("benchmarkReturn") or 0) and (one_month.get("maxDrawdown") or 0) < 0.1:
        return {
            "performanceStatus": "良好",
            "diagnosisText": f"{strategy_name} 短期表现较好，跑赢基准且回撤可控。",
            "suggestedStrategyAction": "保持启用",
        }
    return {
        "performanceStatus": "一般",
        "diagnosisText": f"{strategy_name} 表现处于观察区间，需结合市场状态、交易样本和回撤继续复盘。",
        "suggestedStrategyAction": "降权观察",
    }


def _persist_trade_records(
    strategy_name: str,
    backtest: dict[str, Any],
    timestamp: str,
    source_task_id: int | None = None,
) -> int:
    result_json = _parse_json(backtest.get("result_json"), {})
    trades = result_json.get("trades") or []
    if not trades:
        return 0
    records = []
    for trade in trades:
        entry_date = str(trade.get("date") or trade.get("entry_date") or "")
        if not entry_date:
            continue
        code = str(trade.get("stock_code") or trade.get("code") or "")
        exit_date = str(trade.get("exit_date") or entry_date)
        records.append(
            (
                strategy_name,
                code,
                str(trade.get("name") or code),
                entry_date,
                exit_date,
                _optional_float(trade.get("entry_price")),
                _optional_float(trade.get("exit_price")),
                int(float(trade.get("holding_days") or 1)),
                float(trade.get("return") or trade.get("return_rate") or 0),
                _optional_float(trade.get("max_drawdown_during_holding")),
                str(trade.get("action") or "模拟观察"),
                _optional_float(trade.get("weight")),
                str(trade.get("exit_reason") or trade.get("action") or ""),
                source_task_id,
                timestamp,
            )
        )
    with get_connection() as conn:
        conn.execute("DELETE FROM strategy_trade_records WHERE strategy_name = ?", (strategy_name,))
        conn.executemany(
            """
            INSERT OR REPLACE INTO strategy_trade_records (
                strategy_name, code, name, entry_date, exit_date, entry_price, exit_price,
                holding_days, return_rate, max_drawdown_during_holding, action, weight, exit_reason,
                source_task_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
    return len(records)


def _upsert_summary(performance: dict[str, Any], timestamp: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO strategy_performance_summary (
                strategy_name, period, start_date, end_date, return_rate, annualized_return,
                max_drawdown, volatility, sharpe_ratio, win_rate, trade_count, avg_holding_days,
                benchmark_return, excess_return, data_coverage_ratio, validity_level, warnings_json,
                parameter_hash, data_version, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy_name, period, end_date) DO UPDATE SET
                return_rate = excluded.return_rate,
                annualized_return = excluded.annualized_return,
                max_drawdown = excluded.max_drawdown,
                volatility = excluded.volatility,
                sharpe_ratio = excluded.sharpe_ratio,
                win_rate = excluded.win_rate,
                trade_count = excluded.trade_count,
                avg_holding_days = excluded.avg_holding_days,
                benchmark_return = excluded.benchmark_return,
                excess_return = excluded.excess_return,
                data_coverage_ratio = excluded.data_coverage_ratio,
                validity_level = excluded.validity_level,
                warnings_json = excluded.warnings_json,
                parameter_hash = excluded.parameter_hash,
                data_version = excluded.data_version,
                updated_at = excluded.updated_at
            """,
            (
                performance["strategyName"],
                performance["period"],
                performance["startDate"],
                performance["endDate"],
                performance.get("returnRate"),
                performance.get("annualizedReturn"),
                performance.get("maxDrawdown"),
                performance.get("volatility"),
                performance.get("sharpeRatio"),
                performance.get("winRate"),
                performance.get("tradeCount", 0),
                performance.get("avgHoldingDays"),
                performance.get("benchmarkReturn"),
                performance.get("excessReturn"),
                performance.get("dataCoverageRatio", 0),
                performance.get("validityLevel", "数据不足"),
                json.dumps(performance.get("warnings", []), ensure_ascii=False),
                performance.get("parameterHash", DEFAULT_PARAMETER_HASH),
                performance.get("dataVersion", DEFAULT_DATA_VERSION),
                timestamp,
            ),
        )


def _write_empty_summaries(strategy_name: str, timestamp: str) -> None:
    for period in DEFAULT_PERIODS:
        _upsert_summary(_empty_performance(strategy_name, period), timestamp)


def _empty_performance(strategy_name: str, period: str) -> dict[str, Any]:
    return {
        "strategyName": strategy_name,
        "period": period,
        "startDate": "",
        "endDate": "",
        "startNav": 1,
        "endNav": 1,
        "returnRate": None,
        "annualizedReturn": None,
        "maxDrawdown": None,
        "volatility": None,
        "sharpeRatio": None,
        "winRate": None,
        "tradeCount": 0,
        "avgHoldingDays": None,
        "benchmarkReturn": None,
        "excessReturn": None,
        "dataCoverageRatio": 0,
        "validityLevel": "数据不足",
        "warnings": ["暂无可用回测净值数据。"],
        "parameterHash": DEFAULT_PARAMETER_HASH,
        "dataVersion": DEFAULT_DATA_VERSION,
    }


def _period_from_summary_row(strategy_name: str, period: str, row: dict | None) -> dict[str, Any]:
    if not row:
        return _empty_performance(strategy_name, period)
    return {
        "strategyName": strategy_name,
        "period": period,
        "startDate": row["start_date"],
        "endDate": row["end_date"],
        "returnRate": row["return_rate"],
        "annualizedReturn": row["annualized_return"],
        "maxDrawdown": row["max_drawdown"],
        "volatility": row["volatility"],
        "sharpeRatio": row["sharpe_ratio"],
        "winRate": row["win_rate"],
        "tradeCount": row["trade_count"],
        "avgHoldingDays": row["avg_holding_days"],
        "benchmarkReturn": row["benchmark_return"],
        "excessReturn": row["excess_return"],
        "dataCoverageRatio": row["data_coverage_ratio"],
        "validityLevel": row["validity_level"],
        "warnings": _parse_json(row["warnings_json"], []),
        "parameterHash": row.get("parameter_hash", DEFAULT_PARAMETER_HASH),
        "dataVersion": row.get("data_version", DEFAULT_DATA_VERSION),
        "updatedAt": row["updated_at"],
    }


def _latest_backtests_by_strategy() -> dict[str, dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT br.*, st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            WHERE br.id IN (
                SELECT MAX(br2.id)
                FROM backtest_results br2
                GROUP BY br2.strategy_id
            )
            """
        ).fetchall()
    results = dicts_from_rows(rows)
    for result in results:
        result["result_json"] = _parse_json(result.get("result_json"), {})
    return {result["strategy_name"]: result for result in results}


def _list_strategies() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, type, enabled FROM strategies ORDER BY id").fetchall()
    return dicts_from_rows(rows)


def _has_current_summary(strategy_name: str, end_date: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM strategy_performance_summary
            WHERE strategy_name = ? AND end_date = ? AND period IN ('1M', '3M', '6M', '1Y')
            """,
            (strategy_name, end_date),
        ).fetchone()
    return int(row["c"] or 0) >= 4


def _has_any_summary() -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM strategy_performance_summary").fetchone()
    return bool(row and row["c"])


def _summary_rows(periods: list[str]) -> list[dict]:
    placeholders = ",".join("?" for _ in periods)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT sps.*
            FROM strategy_performance_summary sps
            JOIN (
                SELECT strategy_name, period, MAX(end_date) AS end_date
                FROM strategy_performance_summary
                WHERE period IN ({placeholders})
                GROUP BY strategy_name, period
            ) latest
              ON latest.strategy_name = sps.strategy_name
             AND latest.period = sps.period
             AND latest.end_date = sps.end_date
            """,
            periods,
        ).fetchall()
    return dicts_from_rows(rows)


def _summary_rows_for_strategy(strategy_name: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM strategy_performance_summary
            WHERE strategy_name = ? AND period IN ('1M', '3M', '6M', '1Y')
            ORDER BY period, end_date DESC
            """,
            (strategy_name,),
        ).fetchall()
    latest: dict[str, dict] = {}
    for row in dicts_from_rows(rows):
        latest.setdefault(row["period"], row)
    return list(latest.values())


def _nav_rows(strategy_name: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM strategy_nav_daily
            WHERE strategy_name = ?
            ORDER BY trade_date
            """,
            (strategy_name,),
        ).fetchall()
    return dicts_from_rows(rows)


def _latest_nav_date(strategy_name: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(trade_date) AS d FROM strategy_nav_daily WHERE strategy_name = ?",
            (strategy_name,),
        ).fetchone()
    return row["d"] if row and row["d"] else None


def _nav_count(strategy_name: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM strategy_nav_daily WHERE strategy_name = ?",
            (strategy_name,),
        ).fetchone()
    return int(row["c"] or 0)


def _nav_stats(strategy_name: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS nav_count, MIN(trade_date) AS earliest_date, MAX(trade_date) AS latest_date
            FROM strategy_nav_daily
            WHERE strategy_name = ?
            """,
            (strategy_name,),
        ).fetchone()
    return dict_from_row(row) or {"nav_count": 0, "earliest_date": None, "latest_date": None}


def _trade_records(strategy_name: str, start_date: str, end_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM strategy_trade_records
            WHERE strategy_name = ? AND entry_date >= ? AND entry_date <= ?
            ORDER BY entry_date DESC
            """,
            (strategy_name, start_date, end_date),
        ).fetchall()
    return dicts_from_rows(rows)


def _persisted_trade_count(strategy_name: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM strategy_trade_records WHERE strategy_name = ?",
            (strategy_name,),
        ).fetchone()
    return int(row["c"] or 0)


def _trading_dates(start_date: str, end_date: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT date
            FROM daily_prices
            WHERE date >= ? AND date <= ?
            ORDER BY date
            """,
            (start_date, end_date),
        ).fetchall()
    return [row["date"] for row in rows]


def _latest_market_date() -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(date) AS d FROM daily_prices").fetchone()
    return row["d"] if row and row["d"] else None


def _benchmark_returns(start_date: str, end_date: str) -> dict[str, float]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, AVG(pct_change) / 100.0 AS daily_return
            FROM daily_prices
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
            """,
            (start_date, end_date),
        ).fetchall()
    return {row["date"]: float(row["daily_return"] or 0) for row in rows}


def _period_max_drawdown(nav_values: list[float]) -> float:
    peak = nav_values[0] if nav_values else 1.0
    worst = 0.0
    for value in nav_values:
        peak = max(peak, value)
        drawdown = value / peak - 1 if peak else 0
        worst = min(worst, drawdown)
    return worst


def _performance_overview(rows: list[dict]) -> dict[str, Any]:
    def best(period: str) -> dict[str, Any] | None:
        candidates = [
            row
            for row in rows
            if row["periods"].get(period, {}).get("returnRate") is not None
            and row["periods"].get(period, {}).get("validityLevel") not in {"样本不足", "数据不足"}
        ]
        if not candidates:
            return None
        item = max(candidates, key=lambda row: row["periods"][period]["returnRate"])
        return {"strategyName": item["strategyName"], "returnRate": item["periods"][period]["returnRate"]}

    drawdown_candidates = [row for row in rows if row["periods"].get("1Y", {}).get("maxDrawdown") is not None]
    max_drawdown = max(drawdown_candidates, key=lambda row: row["periods"]["1Y"]["maxDrawdown"]) if drawdown_candidates else None
    return {
        "best1M": best("1M"),
        "best3M": best("3M"),
        "best6M": best("6M"),
        "best1Y": best("1Y"),
        "enabledStrategyCount": sum(1 for row in rows if row["enabled"]),
        "validBacktestStrategyCount": sum(1 for row in rows if row["latestBacktestValidity"] == "可信"),
        "insufficientSampleCount": sum(1 for row in rows if any(period.get("validityLevel") == "样本不足" for period in row["periods"].values())),
        "maxDrawdownStrategy": (
            {"strategyName": max_drawdown["strategyName"], "maxDrawdown": max_drawdown["periods"]["1Y"]["maxDrawdown"]}
            if max_drawdown
            else None
        ),
        "suggestedPauseCount": sum(1 for row in rows if row["suggestedStrategyAction"] == "暂停"),
    }


def _parse_json(raw: object, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not raw:
        return default
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return default


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
