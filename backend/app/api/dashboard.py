from fastapi import APIRouter

from app.services.dashboard_service import dashboard_summary
from app.services.scheduled_job_service import dashboard_latest_or_live
from app.services.strategy_performance_service import get_dashboard_strategy_performance

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard() -> dict:
    return dashboard_summary()


@router.get("/latest")
def get_latest_dashboard() -> dict:
    return dashboard_latest_or_live()


@router.get("/strategy-performance")
def get_dashboard_strategy_performance_summary() -> dict:
    return get_dashboard_strategy_performance()
