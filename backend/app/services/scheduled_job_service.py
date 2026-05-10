from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import AUTO_SCHEDULER_ENABLED, JOB_STALE_MINUTES, JOB_TIMEZONE, MARKET_DATA_SOURCE
from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services import task_service
from app.services.dashboard_service import dashboard_summary
from app.services.market_data_service import sync_market_snapshot, target_trade_date
from app.services.market_service import update_market_data
from app.services.strategy_performance_service import refresh_strategy_performance
from app.services.strategy_service import run_strategies

JOB_DEFINITIONS: list[dict[str, str]] = [
    {
        "job_name": "morning_prewarm_job",
        "job_type": "morning_prewarm",
        "cron_expression": "0 9 * * 1-5",
        "run_time": "09:00",
        "snapshot_type": "morning",
        "description": "开盘前检查数据源、数据库和失败补抓队列，预热上一交易日数据。",
    },
    {
        "job_name": "midday_refresh_job",
        "job_type": "midday_refresh",
        "cron_expression": "35 11 * * 1-5",
        "run_time": "11:35",
        "snapshot_type": "midday",
        "description": "午盘同步行情快照、更新市场状态、候选池和风险观察池。",
    },
    {
        "job_name": "after_close_refresh_job",
        "job_type": "after_close_refresh",
        "cron_expression": "15 15 * * 1-5",
        "run_time": "15:15",
        "snapshot_type": "after_close",
        "description": "收盘后同步完整行情、运行策略、风控和策略收益，生成正式 Dashboard 快照。",
    },
]

_executor = ThreadPoolExecutor(max_workers=1)
_scheduler_lock = threading.Lock()
_scheduler_started = False


def ensure_scheduled_jobs() -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        for definition in JOB_DEFINITIONS:
            conn.execute(
                """
                INSERT INTO scheduled_jobs (
                    job_name, job_type, cron_expression, enabled, timezone, description, created_at, updated_at
                )
                VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(job_name) DO UPDATE SET
                    job_type = excluded.job_type,
                    cron_expression = excluded.cron_expression,
                    timezone = excluded.timezone,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (
                    definition["job_name"],
                    definition["job_type"],
                    definition["cron_expression"],
                    JOB_TIMEZONE,
                    definition["description"],
                    timestamp,
                    timestamp,
                ),
            )


def start_scheduler() -> None:
    global _scheduler_started
    ensure_scheduled_jobs()
    if not AUTO_SCHEDULER_ENABLED:
        return
    _ensure_non_trading_snapshot_from_cache()
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
        thread = threading.Thread(target=_scheduler_loop, name="felix-scheduled-jobs", daemon=True)
        thread.start()


def list_scheduled_jobs() -> list[dict[str, Any]]:
    ensure_scheduled_jobs()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM scheduled_jobs ORDER BY id ASC").fetchall()
    jobs = dicts_from_rows(rows)
    run_time_by_name = {item["job_name"]: item["run_time"] for item in JOB_DEFINITIONS}
    snapshot_by_name = {item["job_name"]: item["snapshot_type"] for item in JOB_DEFINITIONS}
    for job in jobs:
        job["run_time"] = run_time_by_name.get(job["job_name"], "")
        job["snapshot_type"] = snapshot_by_name.get(job["job_name"], "")
    return jobs


def list_job_runs(limit: int = 20, job_name: str | None = None, status: str | None = None, data_date: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if job_name:
        clauses.append("job_name = ?")
        params.append(job_name)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if data_date:
        clauses.append("data_date = ?")
        params.append(data_date)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM job_runs
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
            """,
            [*params, int(limit or 20)],
        ).fetchall()
    return [_decode_job_run(row) for row in rows if row is not None]


def get_job_run(run_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM job_runs WHERE id = ?", (run_id,)).fetchone()
    return _decode_job_run(row)


def latest_jobs_status() -> dict[str, Any]:
    today = target_trade_date()
    runs = list_job_runs(limit=30)
    latest_by_job: dict[str, dict[str, Any] | None] = {}
    for job in list_scheduled_jobs():
        latest_by_job[job["job_name"]] = next((run for run in runs if run["job_name"] == job["job_name"] and run.get("data_date") == today), None)
    latest_success = next((run for run in runs if run["status"] in {"success", "partial_success"}), None)
    latest_failure = next((run for run in runs if run["status"] in {"failed", "failed_timeout"}), None)
    running = [run for run in runs if run["status"] == "running"]
    return {
        "timezone": JOB_TIMEZONE,
        "dataDate": today,
        "schedulerEnabled": AUTO_SCHEDULER_ENABLED,
        "scheduledJobs": list_scheduled_jobs(),
        "todayRuns": latest_by_job,
        "runningRuns": running,
        "latestSuccess": latest_success,
        "latestFailure": latest_failure,
    }


def data_status_overview() -> dict[str, Any]:
    target = target_trade_date()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM data_sync_status ORDER BY updated_at DESC").fetchall()
        stock_count = conn.execute("SELECT COUNT(*) AS c FROM stocks").fetchone()["c"]
        industry_count = conn.execute("SELECT COUNT(DISTINCT industry) AS c FROM stocks WHERE industry != '未分类'").fetchone()["c"]
        latest_price = conn.execute("SELECT MAX(date) AS d FROM daily_prices WHERE date <= ?", (target,)).fetchone()["d"]
        latest_snapshot = conn.execute("SELECT MAX(trade_date) AS d FROM market_snapshots_daily WHERE trade_date <= ?", (target,)).fetchone()["d"]
        failed_stock_count = conn.execute("SELECT COUNT(*) AS c FROM failed_sync_records WHERE status IN ('pending', 'retrying', 'failed')").fetchone()["c"]
        latest_dashboard = conn.execute(
            """
            SELECT data_date, snapshot_type, generated_at
            FROM dashboard_snapshots
            WHERE data_date <= ?
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (target,),
        ).fetchone()
    items = [_decode_data_status(row) for row in rows]
    latest_run = latest_jobs_status().get("latestSuccess")
    data_date = latest_snapshot or latest_price
    is_stale = _is_stale_data_date(data_date)
    if not data_date:
        overall_status = "no_data"
    elif is_stale:
        overall_status = "stale"
    elif latest_run and latest_run.get("status") == "partial_success":
        overall_status = "partial"
    else:
        overall_status = "normal"
    return {
        "overallStatus": overall_status,
        "dataDate": data_date,
        "stockPoolCount": int(stock_count or 0),
        "industryCoverageCount": int(industry_count or 0),
        "latestPriceDate": latest_price,
        "latestSnapshotDate": latest_snapshot,
        "failedStockCount": int(failed_stock_count or 0),
        "latestDashboardSnapshot": dict_from_row(latest_dashboard),
        "items": items,
    }


def start_job(job_name: str, trigger_type: str = "manual", force: bool = False, scheduled_at: str | None = None) -> dict[str, Any]:
    ensure_scheduled_jobs()
    _mark_stale_running_jobs()
    definition = _definition_for_job(job_name)
    if not definition:
        raise ValueError(f"未知任务：{job_name}")
    running = _find_running_job(job_name)
    if running:
        running["reused"] = True
        return running
    data_date = target_trade_date()
    run = _create_job_run(definition, trigger_type=trigger_type, data_date=data_date, scheduled_at=scheduled_at)
    _executor.submit(_run_job, run["id"], definition, force)
    return get_job_run(run["id"]) or run


def build_dashboard_snapshot(snapshot_type: str = "manual", data_date: str | None = None, source_job_run_id: int | None = None) -> dict[str, Any]:
    summary = dashboard_summary()
    target = data_date or summary.get("market_regime", {}).get("tradeDate") or summary.get("last_data_date") or target_trade_date()
    timestamp = now_iso()
    market_status = (summary.get("market_regime") or {}).get("marketRegime") or (summary.get("market_status") or {}).get("summary") or ""
    summary["snapshot_meta"] = {
        "dataDate": target,
        "snapshotType": snapshot_type,
        "generatedAt": timestamp,
        "sourceJobRunId": source_job_run_id,
        "isHistoricalSnapshot": _is_stale_data_date(target),
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO dashboard_snapshots (
                data_date, snapshot_type, generated_at, market_status, market_summary_json,
                candidate_summary_json, risk_summary_json, strategy_summary_json,
                performance_summary_json, data_quality_json, summary_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(data_date, snapshot_type) DO UPDATE SET
                generated_at = excluded.generated_at,
                market_status = excluded.market_status,
                market_summary_json = excluded.market_summary_json,
                candidate_summary_json = excluded.candidate_summary_json,
                risk_summary_json = excluded.risk_summary_json,
                strategy_summary_json = excluded.strategy_summary_json,
                performance_summary_json = excluded.performance_summary_json,
                data_quality_json = excluded.data_quality_json,
                summary_json = excluded.summary_json,
                updated_at = excluded.updated_at
            """,
            (
                target,
                snapshot_type,
                timestamp,
                market_status,
                _json(summary.get("market_regime") or summary.get("market_status") or {}),
                _json({"funnel": summary.get("candidate_funnel"), "layers": summary.get("candidate_layers")}),
                _json({"riskAlerts": summary.get("risk_alerts"), "portfolio": summary.get("portfolio_risk_budget")}),
                _json({"health": summary.get("strategy_health"), "status": summary.get("strategy_decision_status")}),
                _json({"latestBacktest": summary.get("latest_backtest")}),
                _json({"coverage": summary.get("data_coverage"), "quality": summary.get("data_quality")}),
                _json(summary),
                timestamp,
                timestamp,
            ),
        )
    _upsert_data_status("dashboard_snapshot", target, "success", source="local-sqlite", total_count=1, success_count=1)
    return {"dataDate": target, "snapshotType": snapshot_type, "generatedAt": timestamp, "summary": summary}


def latest_dashboard_snapshot() -> dict[str, Any] | None:
    order = "CASE snapshot_type WHEN 'after_close' THEN 1 WHEN 'midday' THEN 2 WHEN 'morning' THEN 3 WHEN 'manual' THEN 4 ELSE 5 END"
    target = target_trade_date()
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT *
            FROM dashboard_snapshots
            WHERE data_date <= ?
            ORDER BY data_date DESC, {order}, generated_at DESC
            LIMIT 1
            """,
            (target,),
        ).fetchone()
    item = dict_from_row(row)
    if not item:
        return None
    item["summary_json"] = _loads(item.get("summary_json"), {})
    return item


def dashboard_latest_or_live() -> dict[str, Any]:
    snapshot = latest_dashboard_snapshot()
    if snapshot and snapshot.get("summary_json"):
        summary = snapshot["summary_json"]
        summary["snapshot_meta"] = {
            **(summary.get("snapshot_meta") or {}),
            "dataDate": snapshot["data_date"],
            "snapshotType": snapshot["snapshot_type"],
            "generatedAt": snapshot["generated_at"],
            "isHistoricalSnapshot": _is_stale_data_date(snapshot["data_date"]),
            "fromDatabaseSnapshot": True,
        }
        return summary
    return _empty_dashboard_snapshot()


def _empty_dashboard_snapshot() -> dict[str, Any]:
    data_status = data_status_overview()
    data_date = data_status.get("dataDate") or target_trade_date()
    generated_at = now_iso()
    stock_pool_count = int(data_status.get("stockPoolCount") or 0)
    market_regime = "Choppy" if stock_pool_count else "RiskOff"
    warning = "尚未生成 Dashboard 数据库快照，请等待后台自动任务完成，或在顶部点击手动刷新数据与策略。"
    return {
        "last_data_date": data_date,
        "last_run_time": None,
        "candidate_count": 0,
        "market_status": {"avg_change": 0.0, "up_count": 0, "total_count": stock_pool_count, "summary": "等待数据库快照"},
        "market_regime": {
            "marketRegime": market_regime,
            "explanation": warning,
            "enabledStrategies": [],
            "reducedStrategies": [],
            "disabledStrategies": ["等待后台快照"],
            "suggestedTotalPosition": 0,
            "indexReturn20d": 0,
            "indexReturn60d": 0,
            "marketVol20d": 0,
            "upStockRatio": 0,
            "limitUpCount": 0,
            "limitDownCount": 0,
            "amountChange20d": 0,
            "sectorRotationStrength": 0,
            "drawdownFromHigh20d": 0,
            "regimeReasons": [warning],
        },
        "daily_decision": {
            "tradeDate": data_date,
            "decisionMode": "WAIT",
            "decisionText": "尚未生成今日策略快照，当前不输出强研究结论。",
            "marketRegime": market_regime,
            "suggestedTotalPositionMin": 0,
            "suggestedTotalPositionMax": 0,
            "allowedActions": ["检查数据中心", "等待后台任务", "手动刷新数据与策略"],
            "forbiddenActions": ["基于空数据做强结论"],
            "keyReasons": [warning],
            "nextCheck": "后台自动任务完成后重新查看 Dashboard。",
            "whyCurrentMode": ["缺少 Dashboard 数据库快照。"],
            "waitingSignals": ["后台自动任务成功", "策略运行结果写入数据库", "候选池快照生成"],
        },
        "position_decision": {
            "baseRiskLimit": 0.65,
            "marketRegimeLimit": 0,
            "strategyQualityLimit": 0,
            "decisionModeLimitMin": 0,
            "decisionModeLimitMax": 0,
            "finalPositionMin": 0,
            "finalPositionMax": 0,
            "mainWatchlistCount": 0,
            "hotspotWatchlistCount": 0,
            "effectiveStrategyCount": 0,
            "highRiskRatio": 0,
            "averageScore": 0,
            "reasons": [warning],
            "explanation": "基础风控上限不是今日建议仓位；缺少策略快照时，今日最终仓位按 0 处理。",
        },
        "candidate_funnel": {
            "rawStockPool": stock_pool_count,
            "baseFiltered": 0,
            "strategyInitialCandidates": 0,
            "hardRiskFiltered": 0,
            "riskPool": 0,
            "defensiveWatchlist": 0,
            "hotspotWatchlist": 0,
            "mainWatchlist": 0,
            "finalActionableCandidates": 0,
            "filterBreakdown": [],
        },
        "candidate_layers": {"mainWatchlist": [], "defensiveWatchlist": [], "hotspotWatchlist": [], "riskPool": [], "reviewPool": []},
        "strategy_health": [],
        "strategy_decision_status": {"activeStrategies": 0, "observeOnlyStrategies": 0, "reviewOnlyStrategies": 0, "pausedStrategies": 0},
        "strategy_distribution": [],
        "candidate_diversity": {
            "repeatRate1d": 0,
            "repeatRate5d": 0,
            "newCandidateCount": 0,
            "droppedCandidateCount": 0,
            "topRepeatedCandidates": [],
            "industryConcentration": 0,
            "strategyConcentration": 0,
            "largeCapRatio": 0,
            "warnings": [warning],
        },
        "market_theme": {"themes": [], "isComplete": False, "confidence": "低", "message": warning, "displayText": "等待数据库快照"},
        "data_coverage": {
            "items": [
                {"name": "Dashboard 快照", "status": "缺失", "reason": warning},
                {"name": "股票池", "status": "已接入" if stock_pool_count else "缺失", "reason": f"当前股票池 {stock_pool_count} 只"},
            ],
            "criticalHotspotDataMissing": True,
            "themeConfidence": "低",
            "warnings": [warning],
        },
        "data_quality": {
            "priceDataUpdated": bool(data_status.get("latestPriceDate")),
            "limitUpDataReady": False,
            "brokenLimitDataReady": False,
            "conceptDataReady": False,
            "financialAnnouncementReady": False,
            "feeIncluded": True,
            "slippageIncluded": True,
            "futureFunctionRisk": "缺少快照时不生成强结论",
            "dataVersion": "local-sqlite",
            "strategyParameterVersion": "scheduled-jobs-v1",
            "integrityScore": 50 if stock_pool_count else 20,
            "integrityLevel": "需谨慎",
            "integrityWarnings": [warning],
        },
        "portfolio_risk_budget": {
            "marketRegime": market_regime,
            "totalSuggestedWeight": 0,
            "portfolioRiskLevel": "中",
            "sectorExposure": {},
            "strategyExposure": {},
            "positions": [],
        },
        "strategy_status": [],
        "latest_backtest": None,
        "current_risk_level": "medium",
        "watchlist": [],
        "defensive_watchlist": [],
        "hotspot_watchlist": [],
        "risk_pool": [],
        "review_pool": [],
        "risk_alerts": [warning],
        "recent_backtests": [],
        "recent_reviews": [],
        "disclaimer": "本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。",
        "snapshot_meta": {
            "dataDate": data_date,
            "snapshotType": "no_snapshot",
            "generatedAt": generated_at,
            "isHistoricalSnapshot": True,
            "fromDatabaseSnapshot": False,
            "warning": warning,
        },
    }


def _scheduler_loop() -> None:
    while True:
        try:
            ensure_scheduled_jobs()
            _mark_stale_running_jobs()
            now = datetime.now(ZoneInfo(JOB_TIMEZONE))
            minute = now.strftime("%H:%M")
            if now.weekday() < 5:
                for definition in JOB_DEFINITIONS:
                    if definition["run_time"] == minute and not _has_auto_run_today(definition["job_name"], now.date().isoformat()):
                        start_job(definition["job_name"], trigger_type="auto", scheduled_at=now.replace(second=0, microsecond=0).isoformat())
        except Exception:
            # The scheduler must never crash the API process. Failures are visible in manual/internal job endpoints.
            pass
        time.sleep(30)


def _run_job(run_id: int, definition: dict[str, str], force: bool) -> None:
    data_date = target_trade_date()
    snapshot_type = definition["snapshot_type"]
    try:
        _update_job_run(run_id, status="running", progress=5, current_stage="checkDataSource：检查数据源、数据库和交易日")
        _upsert_data_status("stock_pool", data_date, "running", source=MARKET_DATA_SOURCE)
        if date.today().weekday() >= 5:
            result = _run_non_trading_cache_job(run_id, data_date)
        elif definition["job_type"] == "morning_prewarm":
            result = _run_morning_job(run_id, data_date, force)
        elif definition["job_type"] == "midday_refresh":
            result = _run_midday_job(run_id, data_date, force)
        else:
            result = _run_after_close_job(run_id, data_date, force)
        _update_job_run(run_id, progress=92, current_stage="buildDashboardSnapshot：生成数据库快照")
        snapshot = build_dashboard_snapshot(snapshot_type=snapshot_type, data_date=data_date, source_job_run_id=run_id)
        status = "partial_success" if int(result.get("failed_count") or 0) else "success"
        _finish_job_run(run_id, status, summary={**result, "snapshot": {key: snapshot[key] for key in ("dataDate", "snapshotType", "generatedAt")}})
    except Exception as exc:  # noqa: BLE001 - job boundary must persist visible failure
        _upsert_data_status("dashboard_snapshot", data_date, "failed", source="local-sqlite", error_message=str(exc))
        _finish_job_run(run_id, "failed", error_message=str(exc), summary={"dataDate": data_date, "snapshotType": snapshot_type})


def _run_non_trading_cache_job(run_id: int, data_date: str) -> dict[str, Any]:
    _update_job_run(run_id, progress=18, current_stage="loadCachedMarketData：非交易日复用上一交易日缓存行情")
    with get_connection() as conn:
        stock_count = conn.execute("SELECT COUNT(*) AS c FROM stocks").fetchone()["c"]
        daily_price_count = conn.execute("SELECT COUNT(*) AS c FROM daily_prices WHERE date = ?", (data_date,)).fetchone()["c"]
        snapshot_count = conn.execute("SELECT COUNT(*) AS c FROM market_snapshots_daily WHERE trade_date = ?", (data_date,)).fetchone()["c"]
    cached_count = int(snapshot_count or daily_price_count or 0)
    if cached_count <= 0:
        raise RuntimeError(f"非交易日缺少 {data_date} 的行情缓存，无法生成研究快照。请先补齐上一交易日行情。")

    _upsert_data_status("stock_pool", data_date, "success", source="local-sqlite-cache", total_count=int(stock_count or 0), success_count=int(stock_count or 0))
    _upsert_data_status("daily_price", data_date, "success", source="local-sqlite-cache", total_count=cached_count, success_count=cached_count)

    _update_job_run(run_id, progress=45, success_count=cached_count, current_stage="runStrategies：基于上一交易日缓存运行策略")
    strategy_result = run_strategies()
    _upsert_data_status("strategy", data_date, "success", source="local-sqlite-cache", total_count=strategy_result.get("strategies_run", 0), success_count=strategy_result.get("strategies_run", 0))

    _update_job_run(run_id, progress=74, current_stage="updateStrategyPerformance：基于缓存刷新策略收益摘要")
    performance = refresh_strategy_performance(force=False)
    _upsert_data_status("nav", data_date, "success", source="local-sqlite-cache", total_count=performance.get("periodsWritten", 0), success_count=performance.get("periodsWritten", 0), failed_count=performance.get("failedCount", 0))
    failed_count = int(performance.get("failedCount") or 0)
    _update_job_run(run_id, failed_count=failed_count, success_count=int(strategy_result.get("signals_created") or cached_count))
    return {
        "job": "non_trading_cache_refresh",
        "dataDate": data_date,
        "stock_count": int(stock_count or 0),
        "cached_count": cached_count,
        "strategy": strategy_result,
        "performance": performance,
        "failed_count": failed_count,
        "note": "非交易日未拉取新行情，已复用上一交易日缓存数据生成研究快照。",
    }


def _run_morning_job(run_id: int, data_date: str, force: bool) -> dict[str, Any]:
    _update_job_run(run_id, progress=20, current_stage="syncStockPool：增量同步股票池和上一交易日快照")
    snapshot = sync_market_snapshot(trade_date=data_date, force=force, limit=1000)
    _upsert_data_status("stock_pool", data_date, "success", source=MARKET_DATA_SOURCE, total_count=snapshot.get("totalCount", 0), success_count=snapshot.get("successCount", 0), failed_count=snapshot.get("failedCount", 0))
    _upsert_data_status("daily_price", data_date, "success", source=MARKET_DATA_SOURCE, total_count=snapshot.get("totalCount", 0), success_count=snapshot.get("successCount", 0), failed_count=snapshot.get("failedCount", 0))
    _update_job_run(run_id, progress=55, current_stage="retryFailedStocks：补抓历史失败股票")
    retry = update_market_data(source="akshare", scope="failed", limit=200)
    failed_count = int(snapshot.get("failedCount") or 0) + int(retry.get("failed_count") or 0)
    _update_job_run(run_id, progress=80, success_count=int(snapshot.get("successCount") or 0), failed_count=failed_count, retry_count=int(retry.get("retry_count") or 0), current_stage="buildDataHealth：输出数据健康度")
    return {"job": "morning_prewarm_job", "snapshot": snapshot, "retry": retry, "failed_count": failed_count}


def _run_midday_job(run_id: int, data_date: str, force: bool) -> dict[str, Any]:
    _update_job_run(run_id, progress=20, current_stage="syncMarketData：同步上午行情快照")
    snapshot = sync_market_snapshot(trade_date=data_date, force=force, limit=3000)
    _upsert_data_status("daily_price", data_date, "success", source=MARKET_DATA_SOURCE, total_count=snapshot.get("totalCount", 0), success_count=snapshot.get("successCount", 0), failed_count=snapshot.get("failedCount", 0))
    _update_job_run(run_id, progress=52, current_stage="runStrategies：生成午盘候选池")
    strategy_result = run_strategies()
    _upsert_data_status("strategy", data_date, "success", source="local-sqlite", total_count=strategy_result.get("strategies_run", 0), success_count=strategy_result.get("strategies_run", 0))
    _update_job_run(run_id, progress=75, current_stage="runRiskEngine：更新风险观察池")
    return {"job": "midday_refresh_job", "snapshot": snapshot, "strategy": strategy_result, "failed_count": int(snapshot.get("failedCount") or 0)}


def _run_after_close_job(run_id: int, data_date: str, force: bool) -> dict[str, Any]:
    _update_job_run(run_id, progress=12, current_stage="syncStockPool：同步全市场股票池和完整日线")
    snapshot = sync_market_snapshot(trade_date=data_date, force=force)
    _upsert_data_status("daily_price", data_date, "success", source=MARKET_DATA_SOURCE, total_count=snapshot.get("totalCount", 0), success_count=snapshot.get("successCount", 0), failed_count=snapshot.get("failedCount", 0))
    _update_job_run(run_id, progress=34, current_stage="retryFailedStocks：优先补抓失败股票")
    retry = update_market_data(source="akshare", scope="failed", limit=200)
    _update_job_run(run_id, progress=50, current_stage="syncTargetStockDaily：增量同步重点股票日线")
    daily = update_market_data(source="akshare", scope="tracked", limit=1200)
    _update_job_run(run_id, progress=66, current_stage="runStrategies：运行所有启用策略")
    strategy_result = run_strategies()
    _upsert_data_status("strategy", data_date, "success", source="local-sqlite", total_count=strategy_result.get("strategies_run", 0), success_count=strategy_result.get("strategies_run", 0))
    _update_job_run(run_id, progress=78, current_stage="updateStrategyPerformance：刷新策略收益和净值摘要")
    performance = refresh_strategy_performance(force=False)
    _upsert_data_status("nav", data_date, "success", source="local-sqlite", total_count=performance.get("periodsWritten", 0), success_count=performance.get("periodsWritten", 0), failed_count=performance.get("failedCount", 0))
    failed_count = int(snapshot.get("failedCount") or 0) + int(retry.get("failed_count") or 0) + int(daily.get("failed_count") or 0) + int(performance.get("failedCount") or 0)
    _update_job_run(run_id, failed_count=failed_count, retry_count=int(retry.get("retry_count") or 0) + int(daily.get("retry_count") or 0), success_count=int(strategy_result.get("signals_created") or 0))
    return {"job": "after_close_refresh_job", "snapshot": snapshot, "retry": retry, "daily": daily, "strategy": strategy_result, "performance": performance, "failed_count": failed_count}


def _create_job_run(definition: dict[str, str], trigger_type: str, data_date: str, scheduled_at: str | None = None) -> dict[str, Any]:
    timestamp = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO job_runs (
                job_name, job_type, trigger_type, status, scheduled_at, started_at,
                progress, current_stage, data_date, snapshot_type, created_at, updated_at
            )
            VALUES (?, ?, ?, 'running', ?, ?, 0, 'pending：后台任务排队中', ?, ?, ?, ?)
            """,
            (
                definition["job_name"],
                definition["job_type"],
                trigger_type,
                scheduled_at,
                timestamp,
                data_date,
                definition["snapshot_type"],
                timestamp,
                timestamp,
            ),
        )
    return get_job_run(int(cursor.lastrowid)) or {}


def _update_job_run(run_id: int, **changes: Any) -> dict[str, Any]:
    allowed = {"status", "progress", "current_stage", "success_count", "failed_count", "retry_count", "error_message", "result_summary"}
    values = {key: value for key, value in changes.items() if key in allowed}
    if not values:
        return get_job_run(run_id) or {}
    if "result_summary" in values and not isinstance(values["result_summary"], str):
        values["result_summary"] = _json(values["result_summary"])
    values["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in values)
    with get_connection() as conn:
        conn.execute(f"UPDATE job_runs SET {assignments} WHERE id = ?", [*values.values(), run_id])
    return get_job_run(run_id) or {}


def _finish_job_run(run_id: int, status: str, summary: dict[str, Any] | None = None, error_message: str | None = None) -> dict[str, Any]:
    run = get_job_run(run_id)
    if not run:
        return {}
    finished_at = now_iso()
    duration_ms = _duration_ms(run.get("started_at"), finished_at)
    progress = 100 if status in {"success", "partial_success"} else run.get("progress", 0)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE job_runs
            SET status = ?, finished_at = ?, duration_ms = ?, progress = ?,
                current_stage = ?, error_message = ?, result_summary = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                finished_at,
                duration_ms,
                progress,
                "completed：自动任务完成" if status in {"success", "partial_success"} else status,
                error_message,
                _json(summary or {}),
                finished_at,
                run_id,
            ),
        )
    return get_job_run(run_id) or {}


def _upsert_data_status(
    data_type: str,
    data_date: str | None,
    status: str,
    total_count: int = 0,
    success_count: int = 0,
    failed_count: int = 0,
    source: str = "",
    error_message: str | None = None,
) -> None:
    timestamp = now_iso()
    last_success_at = timestamp if status == "success" else None
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO data_sync_status (
                data_type, data_date, last_success_at, last_attempt_at, status,
                total_count, success_count, failed_count, source, error_message, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(data_type, data_date) DO UPDATE SET
                last_success_at = COALESCE(excluded.last_success_at, data_sync_status.last_success_at),
                last_attempt_at = excluded.last_attempt_at,
                status = excluded.status,
                total_count = excluded.total_count,
                success_count = excluded.success_count,
                failed_count = excluded.failed_count,
                source = excluded.source,
                error_message = excluded.error_message,
                updated_at = excluded.updated_at
            """,
            (data_type, data_date, last_success_at, timestamp, status, int(total_count or 0), int(success_count or 0), int(failed_count or 0), source, error_message, timestamp, timestamp),
        )


def _find_running_job(job_name: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM job_runs
            WHERE job_name = ? AND status = 'running'
            ORDER BY id DESC
            LIMIT 1
            """,
            (job_name,),
        ).fetchone()
    return _decode_job_run(row)


def _has_auto_run_today(job_name: str, data_date: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM job_runs
            WHERE job_name = ? AND data_date = ? AND trigger_type = 'auto'
              AND status IN ('running', 'success', 'partial_success', 'failed', 'skipped_non_trading_day')
            LIMIT 1
            """,
            (job_name, data_date),
        ).fetchone()
    return bool(row)


def _ensure_non_trading_snapshot_from_cache() -> None:
    if date.today().weekday() < 5:
        return
    data_date = target_trade_date()
    if latest_dashboard_snapshot() or _find_running_job("after_close_refresh_job"):
        return
    with get_connection() as conn:
        cached_count = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM market_snapshots_daily
            WHERE trade_date = ?
            """,
            (data_date,),
        ).fetchone()["c"]
    if int(cached_count or 0) <= 0:
        return
    start_job("after_close_refresh_job", trigger_type="auto", scheduled_at=datetime.now(ZoneInfo(JOB_TIMEZONE)).isoformat())


def _mark_stale_running_jobs() -> None:
    cutoff = datetime.now() - timedelta(minutes=JOB_STALE_MINUTES)
    timestamp = now_iso()
    with get_connection() as conn:
        rows = conn.execute("SELECT id, started_at FROM job_runs WHERE status = 'running'").fetchall()
        for row in rows:
            try:
                started = datetime.fromisoformat(row["started_at"])
            except (TypeError, ValueError):
                started = cutoff - timedelta(seconds=1)
            if started < cutoff:
                conn.execute(
                    """
                    UPDATE job_runs
                    SET status = 'failed_timeout',
                        finished_at = ?,
                        error_message = '后台任务超时未收尾，已自动标记失败。',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (timestamp, timestamp, row["id"]),
                )


def _definition_for_job(job_name: str) -> dict[str, str] | None:
    return next((item for item in JOB_DEFINITIONS if item["job_name"] == job_name), None)


def _decode_job_run(row: Any) -> dict[str, Any] | None:
    item = dict_from_row(row)
    if not item:
        return None
    item["result_summary"] = _loads(item.get("result_summary"), {})
    return item


def _decode_data_status(row: Any) -> dict[str, Any]:
    return dict_from_row(row) or {}


def _loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _duration_ms(started_at: str | None, finished_at: str) -> int:
    if not started_at:
        return 0
    try:
        start = datetime.fromisoformat(started_at)
        finish = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0
    return max(0, int((finish - start).total_seconds() * 1000))


def _is_stale_data_date(data_date: str | None) -> bool:
    if not data_date:
        return True
    try:
        parsed = date.fromisoformat(data_date)
    except ValueError:
        return True
    return parsed < date.fromisoformat(target_trade_date())
