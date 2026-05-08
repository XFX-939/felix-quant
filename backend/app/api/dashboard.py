from fastapi import APIRouter

from app.services.dashboard_service import dashboard_summary
from app.services.strategy_performance_service import get_dashboard_strategy_performance

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard() -> dict:
    return dashboard_summary()


@router.get("/strategy-performance")
def get_dashboard_strategy_performance_summary() -> dict:
    return get_dashboard_strategy_performance()
