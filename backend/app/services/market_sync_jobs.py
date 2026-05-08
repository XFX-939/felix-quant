from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Callable, Any
from uuid import uuid4

from app.db.database import now_iso
from app.services.market_service import update_market_data
from app.services import task_service

SyncUpdateFn = Callable[..., dict[str, Any]]

_executor = ThreadPoolExecutor(max_workers=1)
_lock = Lock()
_jobs: dict[str, dict[str, Any]] = {}
_active_job_id: str | None = None


def start_full_market_sync(
    limit: int | None = None,
    run_inline: bool = False,
    update_fn: SyncUpdateFn = update_market_data,
) -> dict[str, Any]:
    global _active_job_id
    with _lock:
        if _active_job_id:
            active = _jobs.get(_active_job_id)
            if active and active.get("status") in {"pending", "running"}:
                return dict(active)
        job_id = uuid4().hex
        task = task_service.create_task_run("sync_stock_daily", None, total_count=limit or 0, current_stage="queued")
        job = {
            "jobId": job_id,
            "taskId": task["id"],
            "status": "pending",
            "progress": 0,
            "scope": "all",
            "limit": limit,
            "message": "全市场股票池同步已排队",
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "result": None,
            "error": None,
        }
        _jobs[job_id] = job
        _active_job_id = job_id

    if run_inline:
        _run_sync_job(job_id, limit, update_fn)
    else:
        _executor.submit(_run_sync_job, job_id, limit, update_fn)
    return get_sync_job(job_id)


def get_sync_job(job_id: str | None = None) -> dict[str, Any]:
    with _lock:
        target_id = job_id or _active_job_id
        if not target_id or target_id not in _jobs:
            return {
                "jobId": None,
                "taskId": None,
                "status": "idle",
                "progress": 0,
                "scope": "all",
                "limit": None,
                "message": "暂无全市场同步任务",
                "createdAt": None,
                "updatedAt": None,
                "result": None,
                "error": None,
            }
        return dict(_jobs[target_id])


def reset_sync_jobs_for_tests() -> None:
    global _active_job_id
    with _lock:
        _jobs.clear()
        _active_job_id = None


def _run_sync_job(job_id: str, limit: int | None, update_fn: SyncUpdateFn) -> None:
    _patch_job(job_id, status="running", progress=8, message="正在从 AKShare 同步全市场股票列表和日线行情")
    task_id = _job_task_id(job_id)
    if task_id:
        task_service.update_task_run(task_id, status="running", current_stage="sync_stock_daily", progress_percent=8)

    def progress_callback(progress: int, message: str) -> None:
        clamped = max(8, min(99, int(progress)))
        _patch_job(job_id, progress=clamped, message=message)
        current_task_id = _job_task_id(job_id)
        if current_task_id:
            task_service.update_task_run(current_task_id, current_stage=message, progress_percent=clamped)

    try:
        result = update_fn(source="akshare", scope="all", limit=limit, progress_callback=progress_callback)
    except Exception as exc:  # noqa: BLE001 - job boundary should convert any failure to visible status
        _patch_job(job_id, status="failed", progress=100, message="全市场股票池同步失败", error=str(exc))
        if task_id:
            task_service.finish_task_run(task_id, status="failed", error_message=str(exc))
        _clear_active(job_id)
        return
    status = "partial_success" if result.get("failed_count", 0) else "success"
    _patch_job(
        job_id,
        status="completed",
        progress=100,
        message="全市场股票池同步完成",
        result=result,
    )
    if task_id:
        task_service.update_task_run(
            task_id,
            total_count=result.get("stock_count") or limit or 0,
            processed_count=result.get("stock_count") or 0,
            success_count=max(0, int(result.get("stock_count") or 0) - int(result.get("failed_count") or 0)),
            failed_count=result.get("failed_count") or 0,
            retry_count=result.get("retry_count") or 0,
            current_stage="completed",
        )
        task_service.finish_task_run(task_id, status=status, summary=result)
    _clear_active(job_id)


def _patch_job(job_id: str, **changes: Any) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updatedAt"] = now_iso()


def _clear_active(job_id: str) -> None:
    global _active_job_id
    with _lock:
        if _active_job_id == job_id:
            _active_job_id = None


def _job_task_id(job_id: str) -> int | None:
    with _lock:
        job = _jobs.get(job_id)
        task_id = job.get("taskId") if job else None
    return int(task_id) if task_id else None
