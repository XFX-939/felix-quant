from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.config import CRON_SECRET
from app.services import scheduled_job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])
internal_router = APIRouter(prefix="/internal/jobs", tags=["internal-jobs"])


class RunScheduledJobRequest(BaseModel):
    jobName: str
    force: bool = False


def _start_job_response(job_name: str, trigger_type: str, force: bool = False) -> dict[str, Any]:
    try:
        run = scheduled_job_service.start_job(job_name, trigger_type=trigger_type, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"jobRunId": run.get("id"), "jobRun": run}


@router.get("/latest")
def get_latest_jobs_status() -> dict[str, Any]:
    return scheduled_job_service.latest_jobs_status()


@router.get("")
def get_job_runs(
    limit: int = Query(default=20, ge=1, le=100),
    job_name: str | None = None,
    status: str | None = None,
    data_date: str | None = None,
) -> dict[str, Any]:
    return {
        "scheduledJobs": scheduled_job_service.list_scheduled_jobs(),
        "runs": scheduled_job_service.list_job_runs(limit=limit, job_name=job_name, status=status, data_date=data_date),
    }


@router.get("/{run_id}")
def get_job_run(run_id: int) -> dict[str, Any]:
    run = scheduled_job_service.get_job_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="任务不存在")
    return run


@router.post("/run")
def run_scheduled_job(payload: RunScheduledJobRequest) -> dict[str, Any]:
    return _start_job_response(payload.jobName, trigger_type="manual", force=payload.force)


def _verify_cron_secret(authorization: str | None) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET 未配置，内部定时接口不可用。")
    expected = f"Bearer {CRON_SECRET}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="未授权的定时任务请求")


@internal_router.post("/morning-prewarm")
def run_morning_prewarm(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _verify_cron_secret(authorization)
    return _start_job_response("morning_prewarm_job", trigger_type="auto", force=False)


@internal_router.post("/midday-refresh")
def run_midday_refresh(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _verify_cron_secret(authorization)
    return _start_job_response("midday_refresh_job", trigger_type="auto", force=False)


@internal_router.post("/after-close-refresh")
def run_after_close_refresh(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _verify_cron_secret(authorization)
    return _start_job_response("after_close_refresh_job", trigger_type="auto", force=False)
