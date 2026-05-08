from fastapi import APIRouter, Query

from app.services.strategy_performance_service import (
    get_strategy_nav,
    get_strategy_performance_detail,
    get_strategy_performance_summary,
)
from app.services.task_runner import (
    start_strategy_nav_generation,
    start_strategy_performance_refresh,
    start_strategy_summary_refresh,
)

router = APIRouter(prefix="/strategy-performance", tags=["strategy-performance"])


@router.get("/summary")
def strategy_performance_summary(
    periods: str | None = Query(default=None),
    strategyNames: str | None = Query(default=None),
    benchmarkCode: str | None = Query(default=None),
) -> dict:
    return get_strategy_performance_summary(
        periods=_split_csv(periods),
        strategy_names=_split_csv(strategyNames),
        benchmark_code=benchmarkCode,
    )


@router.get("/nav")
def strategy_performance_nav(
    strategyNames: str | None = Query(default=None),
    period: str = Query(default="1Y"),
    benchmarkCode: str | None = Query(default=None),
) -> dict:
    return get_strategy_nav(strategy_names=_split_csv(strategyNames), period=period, benchmark_code=benchmarkCode)


@router.get("/detail/{strategy_name:path}")
def strategy_performance_detail(strategy_name: str, period: str = Query(default="1Y")) -> dict:
    return get_strategy_performance_detail(strategy_name, period=period)


@router.post("/refresh")
def refresh_strategy_performance(force: bool = Query(default=False)) -> dict:
    task = start_strategy_performance_refresh(force=force)
    return {"taskId": task["id"], "task": task}


@router.post("/generate-nav")
def generate_strategy_nav(payload: dict | None = None) -> dict:
    payload = payload or {}
    task = start_strategy_nav_generation(
        strategy_name=payload.get("strategyName"),
        start_date=payload.get("startDate"),
        end_date=payload.get("endDate"),
        force=bool(payload.get("force", False)),
    )
    return {"taskId": task["id"], "task": task}


@router.post("/refresh-summary")
def refresh_strategy_summary(payload: dict | None = None) -> dict:
    payload = payload or {}
    task = start_strategy_summary_refresh(
        strategy_name=payload.get("strategyName"),
        end_date=payload.get("endDate"),
        force=bool(payload.get("force", False)),
    )
    return {"taskId": task["id"], "task": task}


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]
