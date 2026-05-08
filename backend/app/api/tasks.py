from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import task_runner, task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


class DailyPipelinePayload(BaseModel):
    tradeDate: str | None = None
    force: bool = False
    dryRun: bool = False


class RetryFailedPayload(BaseModel):
    tradeDate: str | None = None
    taskType: str | None = None


@router.post("/run-daily-pipeline")
def run_daily_pipeline(payload: DailyPipelinePayload) -> dict[str, Any]:
    task = task_runner.start_daily_pipeline(payload.tradeDate, force=payload.force, dry_run=payload.dryRun)
    return {"taskId": task["id"], "task": task}


@router.post("/retry-failed-stocks")
def retry_failed_stocks(payload: RetryFailedPayload) -> dict[str, Any]:
    task = task_runner.start_retry_failed_stocks(payload.tradeDate, payload.taskType)
    return {"taskId": task["id"], "task": task}


@router.post("/run-backtest")
def run_backtest_task(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("strategy_id"):
        raise HTTPException(status_code=400, detail="strategy_id is required")
    task = task_runner.start_backtest_task(payload)
    return {"taskId": task["id"], "task": task}


@router.post("/run-batch-backtest")
def run_batch_backtest_task(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("strategyNames") and not payload.get("strategyIds") and not payload.get("enabledOnly"):
        raise HTTPException(status_code=400, detail="请至少选择一个策略。")
    try:
        task = task_runner.start_batch_backtest_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"taskId": task["id"], "task": task}


@router.get("")
def list_tasks(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    return task_service.list_task_runs(limit=limit)


@router.get("/{task_id}")
def get_task(task_id: int) -> dict[str, Any]:
    task = task_service.get_task_run(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task
