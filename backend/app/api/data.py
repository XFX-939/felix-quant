from fastapi import APIRouter, HTTPException, Query

from app.services.akshare_provider import AkshareUnavailableError
from app.services.market_service import update_market_data
from app.services.market_sync_jobs import get_sync_job, start_full_market_sync
from app.services.scheduled_job_service import data_status_overview
from app.services.strategy_service import run_strategies

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/update")
def update_data_and_run(
    source: str | None = Query(default=None, description="akshare 或 sample"),
    scope: str | None = Query(default=None, description="tracked 或 all"),
    limit: int | None = Query(default=None, ge=1, le=6000),
) -> dict:
    active_job = get_sync_job()
    if active_job.get("status") in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="全市场同步正在进行，请等待完成后再运行策略。")
    try:
        data_result = update_market_data(source=source, scope=scope, limit=limit)
    except (AkshareUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    strategy_result = run_strategies()
    source_name = "AKShare 真实行情" if data_result.get("source") == "akshare" else "示例行情"
    return {
        "data": data_result,
        "strategy": strategy_result,
        "message": f"{source_name}已更新，启用策略已执行。",
    }


@router.post("/sync/full-market")
def start_full_market_data_sync(
    limit: int | None = Query(default=None, ge=1, le=6000),
) -> dict:
    return start_full_market_sync(limit=limit)


@router.get("/sync/full-market")
def get_full_market_data_sync_status(job_id: str | None = Query(default=None)) -> dict:
    return get_sync_job(job_id)


@router.get("/status")
def get_data_status() -> dict:
    return data_status_overview()
