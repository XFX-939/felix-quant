from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from app.services.backtest_service import run_backtest
from app.services.market_service import update_market_data
from app.services.market_data_service import is_market_snapshot_synced, sync_market_snapshot, target_trade_date
from app.services.strategy_performance_service import (
    generate_strategy_nav_from_backtests,
    refresh_strategy_performance,
    refresh_strategy_performance_summary,
)
from app.services.strategy_service import list_strategies
from app.services.strategy_service import run_strategies
from app.services import task_service

_executor = ThreadPoolExecutor(max_workers=2)


def start_daily_pipeline(trade_date: str | None = None, force: bool = False, dry_run: bool = False) -> dict[str, Any]:
    target_date = trade_date or date.today().isoformat()
    running = task_service.find_running_task("run_daily_pipeline", target_date)
    if running:
        running["reused"] = True
        return running
    task = task_service.create_task_run("run_daily_pipeline", target_date, total_count=12, current_stage="排队：每日决策流水线")
    _executor.submit(_run_daily_pipeline, task["id"], target_date, force, dry_run)
    return task


def start_market_snapshot_sync(trade_date: str | None = None, force: bool = False, limit: int | None = None) -> dict[str, Any]:
    target_date = trade_date or target_trade_date()
    running = task_service.find_running_task("sync_market_snapshot", target_date)
    if running:
        running["reused"] = True
        return running
    if not force and is_market_snapshot_synced(target_date):
        return {
            "id": 0,
            "task_type": "sync_market_snapshot",
            "trade_date": target_date,
            "status": "success",
            "current_stage": "今日行情已同步",
            "total_count": 0,
            "processed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "retry_count": 0,
            "progress_percent": 100,
            "started_at": None,
            "finished_at": None,
            "duration_ms": 0,
            "error_message": None,
            "summary_json": {"skipped": True},
            "created_by": "system",
            "created_at": "",
            "updated_at": "",
            "reused": True,
        }
    task = task_service.create_task_run("sync_market_snapshot", target_date, total_count=limit or 5000, current_stage="排队：全市场行情入库")
    _executor.submit(_run_market_snapshot_sync, task["id"], target_date, force, limit)
    return task


def start_retry_failed_stocks(trade_date: str | None = None, task_type: str | None = None) -> dict[str, Any]:
    target_date = trade_date or date.today().isoformat()
    running = task_service.find_running_task("retry_failed_stocks", target_date)
    if running:
        running["reused"] = True
        return running
    pending = task_service.pending_failed_stock_codes(trade_date=trade_date, task_type=task_type or "sync_stock_daily")
    if not pending:
        pending = task_service.pending_failed_stock_codes(task_type=task_type or "sync_stock_daily")
    task = task_service.create_task_run(
        "retry_failed_stocks",
        target_date,
        total_count=max(1, len(pending)),
        current_stage="排队：失败股票补抓",
    )
    _executor.submit(_run_retry_failed_stocks, task["id"], target_date, len(pending))
    return task


def start_backtest_task(payload: dict[str, Any]) -> dict[str, Any]:
    target_date = payload.get("end_date") or date.today().isoformat()
    strategy_id = payload.get("strategy_id")
    task_type = f"run_backtest:{strategy_id}"
    running = task_service.find_running_task(task_type, target_date)
    if running:
        running["reused"] = True
        return running
    task = task_service.create_task_run(task_type, target_date, total_count=10, current_stage="排队：回测")
    _executor.submit(_run_backtest_task, task["id"], payload)
    return task


def start_batch_backtest_task(payload: dict[str, Any]) -> dict[str, Any]:
    target_date = payload.get("endDate") or payload.get("end_date") or date.today().isoformat()
    running = task_service.find_running_task("batch_backtest", target_date)
    if running:
        running["reused"] = True
        return running
    strategies = _resolve_batch_strategies(payload)
    if not strategies:
        raise ValueError("请至少选择一个策略。")
    task = task_service.create_task_run(
        "batch_backtest",
        target_date,
        total_count=len(strategies),
        current_stage="排队：批量回测",
        child_task_count=len(strategies),
        batch_mode=True,
        task_group_name=payload.get("taskGroupName") or "批量回测",
    )
    _executor.submit(_run_batch_backtest_task, task["id"], payload, strategies)
    return task


def start_strategy_performance_refresh(force: bool = False) -> dict[str, Any]:
    target_date = date.today().isoformat()
    running = task_service.find_running_task("refresh_strategy_performance", target_date)
    if running:
        running["reused"] = True
        return running
    task = task_service.create_task_run(
        "refresh_strategy_performance",
        target_date,
        total_count=8,
        current_stage="排队：更新策略收益",
    )
    _executor.submit(_run_strategy_performance_refresh, task["id"], target_date, force)
    return task


def start_strategy_nav_generation(
    strategy_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    target_date = end_date or date.today().isoformat()
    task_type = "generate_strategy_nav" if not strategy_name else f"generate_strategy_nav:{strategy_name}"
    running = task_service.find_running_task(task_type, target_date)
    if running:
        running["reused"] = True
        return running
    task = task_service.create_task_run(task_type, target_date, total_count=7, current_stage="排队：生成策略每日净值")
    _executor.submit(_run_strategy_nav_generation, task["id"], strategy_name, start_date, end_date, force)
    return task


def start_strategy_summary_refresh(strategy_name: str | None = None, end_date: str | None = None, force: bool = False) -> dict[str, Any]:
    target_date = end_date or date.today().isoformat()
    task_type = "refresh_strategy_summary" if not strategy_name else f"refresh_strategy_summary:{strategy_name}"
    running = task_service.find_running_task(task_type, target_date)
    if running:
        running["reused"] = True
        return running
    task = task_service.create_task_run(task_type, target_date, total_count=4, current_stage="排队：刷新策略收益汇总")
    _executor.submit(_run_strategy_summary_refresh, task["id"], strategy_name, end_date, force)
    return task


def _run_daily_pipeline(task_id: int, trade_date: str, force: bool, dry_run: bool) -> None:
    try:
        _stage(task_id, 1, "sync_market_snapshot", "同步市场快照")
        _stage(task_id, 2, "build_target_symbols", "构建重点股票池")
        _stage(task_id, 3, "retry_failed_stocks", "优先补抓失败股票")
        retry_result = update_market_data(source="akshare", scope="failed", limit=200)
        _stage(task_id, 4, "sync_target_stock_daily", "增量同步重点股票日线")
        sync_result = {} if dry_run else update_market_data(source="akshare", scope="tracked", limit=1200)
        _stage(task_id, 5, "compute_target_factors", "计算目标股票因子")
        _stage(task_id, 6, "detect_market_regime", "识别市场状态")
        _stage(task_id, 7, "detect_market_theme", "识别市场主线")
        _stage(task_id, 8, "run_enabled_strategies", "运行启用策略")
        strategy_result = {"signals_created": 0, "strategies_run": 0} if dry_run else run_strategies()
        _stage(task_id, 9, "apply_risk_engine", "应用风险约束")
        _stage(task_id, 10, "generate_daily_decision", "生成今日决策结论")
        _stage(task_id, 11, "persist_results", "持久化结果")
        _stage(task_id, 12, "refresh_strategy_performance", "刷新策略收益汇总")
        performance_result = refresh_strategy_performance(force=False)
        failed_count = int(sync_result.get("failed_count") or 0) + int(retry_result.get("failed_count") or 0)
        status = "partial_success" if failed_count else "success"
        task_service.update_task_run(
            task_id,
            processed_count=12,
            success_count=12 - (1 if failed_count else 0),
            failed_count=failed_count,
            retry_count=int(sync_result.get("retry_count") or 0) + int(retry_result.get("retry_count") or 0),
            current_stage="completed",
        )
        task_service.finish_task_run(
            task_id,
            status=status,
            summary={
                "tradeDate": trade_date,
                "sync": sync_result,
                "retry": retry_result,
                "strategy": strategy_result,
                "performance": {
                    "navGeneratedCount": 0,
                    "summaryRefreshedCount": performance_result.get("periodsWritten", 0),
                    "missingNavStrategies": [],
                    "failedStrategies": performance_result.get("failed", []),
                },
                "force": force,
                "dryRun": dry_run,
            },
        )
    except Exception as exc:  # noqa: BLE001 - async task boundary must persist visible failure
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"tradeDate": trade_date})


def _run_market_snapshot_sync(task_id: int, trade_date: str, force: bool, limit: int | None) -> None:
    try:
        def progress(progress_percent: int, message: str) -> None:
            task_service.update_task_run(
                task_id,
                status="running",
                current_stage=message,
                progress_percent=min(99, max(0, progress_percent)),
            )

        result = sync_market_snapshot(trade_date=trade_date, force=force, limit=limit, task_id=task_id, progress_callback=progress)
        task_service.update_task_run(
            task_id,
            processed_count=int(result.get("successCount") or result.get("totalCount") or 0),
            success_count=int(result.get("successCount") or 0),
            failed_count=int(result.get("failedCount") or 0),
            current_stage="全市场行情同步完成",
        )
        task_service.finish_task_run(task_id, status="success", summary=result)
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"tradeDate": trade_date})


def _run_retry_failed_stocks(task_id: int, trade_date: str, total_count: int) -> None:
    try:
        task_service.update_task_run(task_id, status="running", current_stage="补抓失败股票", total_count=max(1, total_count))
        result = update_market_data(source="akshare", scope="failed", limit=max(1, total_count) if total_count else 200)
        failed_count = int(result.get("failed_count") or 0)
        task_service.update_task_run(
            task_id,
            processed_count=int(result.get("stock_count") or total_count or 0),
            success_count=max(0, int(result.get("stock_count") or 0) - failed_count),
            failed_count=failed_count,
            retry_count=int(result.get("retry_count") or 0),
            current_stage="completed",
        )
        task_service.finish_task_run(task_id, status="partial_success" if failed_count else "success", summary={"tradeDate": trade_date, "sync": result})
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"tradeDate": trade_date})


def _run_backtest_task(task_id: int, payload: dict[str, Any]) -> None:
    try:
        _execute_backtest_task(task_id, payload, refresh_performance=True)
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"payload": payload})


def _run_batch_backtest_task(task_id: int, payload: dict[str, Any], strategies: list[dict[str, Any]]) -> None:
    child_results: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    try:
        task_service.update_task_run(
            task_id,
            status="running",
            current_stage="batch_validate：校验批量回测参数",
            total_count=len(strategies),
            child_task_count=len(strategies),
        )
        for index, strategy in enumerate(strategies, start=1):
            child_payload = _batch_payload_for_strategy(payload, strategy)
            child = task_service.create_task_run(
                f"run_backtest:{strategy['id']}",
                payload.get("endDate") or payload.get("end_date") or date.today().isoformat(),
                total_count=10,
                current_stage="排队：批量子回测",
                parent_task_id=task_id,
                strategy_name=strategy["name"],
                task_group_name=f"批量回测 #{task_id}",
            )
            task_service.update_task_run(
                task_id,
                status="running",
                processed_count=index - 1,
                completed_child_count=success_count + failed_count,
                failed_child_count=failed_count,
                current_stage=f"batch_running：正在回测 {strategy['name']} ({index}/{len(strategies)})",
            )
            try:
                result = _execute_backtest_task(child["id"], child_payload, refresh_performance=False)
                success_count += 1
                child_results.append(_batch_result_summary(strategy, result, "success"))
            except Exception as exc:  # noqa: BLE001 - one strategy must not stop the whole batch
                failed_count += 1
                task_service.finish_task_run(
                    child["id"],
                    status="failed",
                    error_message=str(exc),
                    summary={"strategyName": strategy["name"], "payload": child_payload},
                )
                child_results.append({"strategyName": strategy["name"], "strategyId": strategy["id"], "status": "failed", "error": str(exc)})
            task_service.update_task_run(
                task_id,
                processed_count=index,
                success_count=success_count,
                failed_count=failed_count,
                completed_child_count=success_count + failed_count,
                failed_child_count=failed_count,
                current_stage=f"batch_progress：已完成 {success_count + failed_count}/{len(strategies)} 个策略",
            )

        task_service.update_task_run(task_id, current_stage="batch_refresh：刷新策略收益汇总")
        performance = refresh_strategy_performance(force=True)
        validity = _batch_validity(payload, child_results)
        status = "success" if failed_count == 0 else ("failed" if success_count == 0 else "partial_success")
        task_service.finish_task_run(
            task_id,
            status=status,
            summary={
                "taskType": "batch_backtest",
                "strategyCount": len(strategies),
                "successCount": success_count,
                "failedCount": failed_count,
                "stockPool": payload.get("stockPool") or payload.get("stock_pool"),
                "startDate": payload.get("startDate") or payload.get("start_date"),
                "endDate": payload.get("endDate") or payload.get("end_date"),
                "results": child_results,
                "validity": validity,
                "performance": performance,
            },
        )
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(
            task_id,
            status="failed",
            error_message=str(exc),
            summary={"strategyCount": len(strategies), "successCount": success_count, "failedCount": failed_count, "results": child_results},
        )


def _execute_backtest_task(task_id: int, payload: dict[str, Any], refresh_performance: bool) -> dict[str, Any]:
    total_count = 10
    _stage(task_id, 1, "validate_params", "检查回测参数", total_count=total_count)
    _stage(task_id, 2, "validate_data_coverage", "检查数据覆盖率", total_count=total_count)
    _stage(task_id, 3, "load_local_prices", "加载历史行情", total_count=total_count)
    _stage(task_id, 4, "generate_trade_signals", "生成交易信号", total_count=total_count)
    _stage(task_id, 5, "simulate_trades", "模拟交易撮合", total_count=total_count)
    result = run_backtest(payload)
    result_json = result.get("result_json") or {}
    trade_count = int(result.get("trade_count") or 0)
    signal_count = len(result_json.get("trades") or [])
    trading_days = len(result_json.get("equity_curve") or [])
    stock_count = int(result_json.get("stock_count") or 0)
    task_service.update_task_run(
        task_id,
        total_count=total_count,
        processed_count=6,
        success_count=signal_count,
        current_stage="calculate_return_drawdown：计算收益与回撤",
    )
    _stage(task_id, 7, "calculate_statistics", "计算胜率、夏普、盈亏比", total_count=total_count)
    _stage(task_id, 8, "check_validity", "执行回测可信度检查", total_count=total_count)
    _stage(task_id, 9, "persist_backtest", "写入回测结果", total_count=total_count)
    performance = {}
    if refresh_performance:
        _stage(task_id, 10, "refresh_strategy_performance", "刷新策略收益汇总", total_count=total_count)
        performance = refresh_strategy_performance(force=True)
    else:
        task_service.update_task_run(task_id, processed_count=10, current_stage="completed")
    task_service.update_task_run(
        task_id,
        processed_count=total_count,
        success_count=max(signal_count, trade_count),
        failed_count=0,
        current_stage="completed",
    )
    task_service.finish_task_run(
        task_id,
        status="success",
        summary={
            "backtestResultId": result.get("id"),
            "strategyName": result.get("strategy_name"),
            "stockCount": stock_count,
            "tradingDays": trading_days,
            "signalCount": signal_count,
            "tradeCount": trade_count,
            "validity": result.get("validity"),
            "performance": performance,
        },
    )
    return result


def _run_strategy_performance_refresh(task_id: int, trade_date: str, force: bool) -> None:
    try:
        stages = [
            ("load_strategies", "加载策略列表"),
            ("check_nav_data", "检查策略净值数据"),
            ("generate_missing_nav", "生成缺失净值"),
            ("calculate_period_return", "计算各周期收益"),
            ("calculate_risk_metrics", "计算回撤、胜率、夏普"),
            ("update_summary", "更新 summary 表"),
            ("generate_diagnosis", "生成诊断结论"),
            ("completed", "完成"),
        ]
        for index, (stage, label) in enumerate(stages[:2], start=1):
            _stage(task_id, index, stage, label, total_count=len(stages))

        def progress(progress_percent: int, message: str) -> None:
            processed = min(len(stages) - 1, max(3, int(progress_percent / 100 * len(stages))))
            task_service.update_task_run(
                task_id,
                status="running",
                current_stage=message,
                total_count=len(stages),
                processed_count=processed,
            )

        result = refresh_strategy_performance(force=force, progress_callback=progress)
        _stage(task_id, 8, "completed", "完成", total_count=len(stages))
        failed_count = int(result.get("failedCount") or 0)
        task_service.update_task_run(
            task_id,
            processed_count=len(stages),
            success_count=max(0, int(result.get("successCount") or 0)),
            failed_count=failed_count,
            current_stage="completed",
        )
        task_service.finish_task_run(
            task_id,
            status="partial_success" if failed_count else "success",
            summary={"tradeDate": trade_date, "performance": result, "force": force},
        )
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"tradeDate": trade_date, "force": force})


def _run_strategy_nav_generation(
    task_id: int,
    strategy_name: str | None,
    start_date: str | None,
    end_date: str | None,
    force: bool,
) -> None:
    try:
        stages = [
            ("load_local_prices", "加载历史数据"),
            ("generate_signals", "生成交易信号"),
            ("simulate_portfolio", "模拟持仓收益"),
            ("generate_nav", "生成每日净值"),
            ("generate_trades", "生成交易记录"),
            ("refresh_summary", "刷新策略收益汇总"),
            ("completed", "完成"),
        ]
        for index, (stage, label) in enumerate(stages[:2], start=1):
            _stage(task_id, index, stage, label, total_count=len(stages))

        def progress(progress_percent: int, message: str) -> None:
            processed = min(len(stages) - 1, max(3, int(progress_percent / 100 * len(stages))))
            task_service.update_task_run(
                task_id,
                status="running",
                current_stage=message,
                total_count=len(stages),
                processed_count=processed,
            )

        result = generate_strategy_nav_from_backtests(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            force=force,
            progress_callback=progress,
            source_task_id=task_id,
        )
        _stage(task_id, len(stages), "completed", "完成", total_count=len(stages))
        failed_count = int(result.get("failedCount") or 0)
        task_service.update_task_run(
            task_id,
            processed_count=len(stages),
            success_count=max(0, int(result.get("strategyCount") or 0) - failed_count),
            failed_count=failed_count,
            current_stage="completed",
        )
        task_service.finish_task_run(
            task_id,
            status="partial_success" if failed_count else "success",
            summary={"strategyName": strategy_name, "startDate": start_date, "endDate": end_date, "force": force, "performance": result},
        )
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"strategyName": strategy_name, "force": force})


def _run_strategy_summary_refresh(task_id: int, strategy_name: str | None, end_date: str | None, force: bool) -> None:
    try:
        _stage(task_id, 1, "load_strategy_nav", "读取策略每日净值", total_count=4)
        _stage(task_id, 2, "calculate_periods", "计算周期收益", total_count=4)

        def progress(progress_percent: int, message: str) -> None:
            processed = min(3, max(2, int(progress_percent / 100 * 4)))
            task_service.update_task_run(task_id, status="running", current_stage=message, total_count=4, processed_count=processed)

        result = refresh_strategy_performance_summary(strategy_name=strategy_name, end_date=end_date, force=force, progress_callback=progress)
        _stage(task_id, 4, "completed", "完成", total_count=4)
        failed_count = int(result.get("failedCount") or 0)
        task_service.update_task_run(
            task_id,
            processed_count=4,
            success_count=max(0, int(result.get("strategyCount") or 0) - failed_count),
            failed_count=failed_count,
            current_stage="completed",
        )
        task_service.finish_task_run(
            task_id,
            status="partial_success" if failed_count else "success",
            summary={"strategyName": strategy_name, "endDate": end_date, "force": force, "performance": result},
        )
    except Exception as exc:  # noqa: BLE001
        task_service.finish_task_run(task_id, status="failed", error_message=str(exc), summary={"strategyName": strategy_name, "force": force})


def _resolve_batch_strategies(payload: dict[str, Any]) -> list[dict[str, Any]]:
    all_strategies = list_strategies()
    by_name = {strategy["name"]: strategy for strategy in all_strategies}
    by_id = {int(strategy["id"]): strategy for strategy in all_strategies}
    selected: list[dict[str, Any]] = []
    for strategy_id in payload.get("strategyIds") or payload.get("strategy_ids") or []:
        strategy = by_id.get(int(strategy_id))
        if strategy:
            selected.append(strategy)
    for name in payload.get("strategyNames") or payload.get("strategy_names") or []:
        strategy = by_name.get(str(name))
        if strategy:
            selected.append(strategy)
    if not selected and payload.get("enabledOnly"):
        selected = [strategy for strategy in all_strategies if strategy.get("enabled")]
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for strategy in selected:
        strategy_id = int(strategy["id"])
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        unique.append(strategy)
    return unique


def _batch_payload_for_strategy(payload: dict[str, Any], strategy: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": int(strategy["id"]),
        "stock_pool": payload.get("stockPool") or payload.get("stock_pool") or "today_candidates",
        "start_date": payload.get("startDate") or payload.get("start_date"),
        "end_date": payload.get("endDate") or payload.get("end_date"),
        "initial_cash": payload.get("initialCapital") or payload.get("initial_cash") or 100000,
        "fee_rate": payload.get("transactionCost") or payload.get("fee_rate") or 0.0003,
        "slippage": payload.get("slippage") if payload.get("slippage") is not None else 0.001,
        "stop_loss": payload.get("stopLoss") or payload.get("stop_loss") or 0.08,
        "take_profit": payload.get("takeProfit") or payload.get("take_profit") or 0.12,
        "position_cap": payload.get("maxPositionPerStock") or payload.get("position_cap") or 0.2,
        "max_positions": payload.get("maxHoldingCount") or payload.get("max_positions") or 3,
        "max_holding_days": payload.get("maxHoldingDays") or payload.get("max_holding_days") or 5,
    }


def _batch_result_summary(strategy: dict[str, Any], result: dict[str, Any], status: str) -> dict[str, Any]:
    result_json = result.get("result_json") or {}
    validity = result.get("validity") or {}
    return {
        "strategyId": strategy["id"],
        "strategyName": result.get("strategy_name") or strategy["name"],
        "status": status,
        "backtestResultId": result.get("id"),
        "totalReturn": result.get("total_return"),
        "annualReturn": result.get("annual_return"),
        "maxDrawdown": result.get("max_drawdown"),
        "sharpe": result.get("sharpe"),
        "winRate": result.get("win_rate"),
        "profitLossRatio": result_json.get("profit_loss_ratio"),
        "tradeCount": result.get("trade_count"),
        "avgHoldingDays": result_json.get("avg_holding_days"),
        "validityLevel": validity.get("validityLevel"),
        "equityCurve": result_json.get("equity_curve") or [],
    }


def _batch_validity(payload: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in results if item.get("status") == "success"]
    total = max(1, len(results))
    insufficient = sum(1 for item in successful if int(item.get("tradeCount") or 0) < 30)
    data_insufficient = sum(1 for item in successful if item.get("validityLevel") == "数据不足")
    sample_pool = (payload.get("stockPool") or payload.get("stock_pool")) == "sample"
    warnings: list[str] = ["批量回测用于横向比较策略表现，不代表未来收益。"]
    if sample_pool:
        level = "仅功能验证"
        warnings.append("当前股票池为示例股票池，仅用于功能验证。")
    elif data_insufficient:
        level = "数据不足"
        warnings.append("部分策略历史行情覆盖不足。")
    elif insufficient > total / 2:
        level = "样本不足"
        warnings.append("超过一半策略交易次数不足 30，统计意义较弱。")
    elif any(item.get("validityLevel") == "需谨慎" for item in successful):
        level = "需谨慎"
        warnings.append("部分策略存在幸存者偏差、前视偏差或交易成本口径风险。")
    else:
        level = "可信" if successful else "数据不足"
    return {
        "validityLevel": level,
        "warnings": warnings,
        "validStrategyCount": sum(1 for item in successful if item.get("validityLevel") == "可信"),
        "insufficientSampleStrategyCount": insufficient,
        "dataInsufficientStrategyCount": data_insufficient,
    }


def _stage(task_id: int, processed: int, stage: str, label: str, total_count: int = 11) -> None:
    task_service.update_task_run(
        task_id,
        status="running",
        current_stage=f"{stage}：{label}",
        total_count=total_count,
        processed_count=processed,
    )
