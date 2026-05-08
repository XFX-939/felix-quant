from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services import task_runner
from app.services.limit_up_strategy_service import (
    generate_limit_up_strategy_analysis,
    get_industry_heat,
    get_limit_up_strategy_signals,
    get_market_sentiment,
)
from app.services.market_data_service import get_limit_up_summary, get_market_data_sync_status

router = APIRouter(prefix="/market-data", tags=["market-data"])
limit_router = APIRouter(prefix="/limit-up-stats", tags=["limit-up-stats"])
limit_strategy_router = APIRouter(prefix="/limit-up-strategy", tags=["limit-up-strategy"])


@router.get("/sync-status")
def market_data_sync_status(tradeDate: str | None = Query(default=None)) -> dict[str, Any]:
    return get_market_data_sync_status(tradeDate)


@router.post("/sync")
def start_market_data_sync(
    tradeDate: str | None = Query(default=None),
    force: bool = Query(default=False),
    limit: int | None = Query(default=None, ge=1, le=6000),
) -> dict[str, Any]:
    task = task_runner.start_market_snapshot_sync(tradeDate, force=force, limit=limit)
    return {"taskId": task.get("id") or None, "task": task, "status": get_market_data_sync_status(tradeDate)}


@limit_router.get("")
def limit_up_stats(
    date: str | None = Query(default=None),
    height: str = Query(default="all"),
    market: str = Query(default="all"),
    search: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    action_label: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    exclude_st: bool = Query(default=False),
    mainline_only: bool = Query(default=False),
) -> dict[str, Any]:
    return generate_limit_up_strategy_analysis(
        trade_date=date,
        height_filter=height,
        market_filter=market,
        search=search,
        industry=industry,
        action_label=action_label,
        min_score=min_score,
        exclude_st=exclude_st,
        mainline_only=mainline_only,
    )


@limit_router.get("/summary")
def limit_up_summary(date: str | None = Query(default=None)) -> dict[str, Any]:
    return get_limit_up_summary(date)


@limit_router.get("/market-sentiment")
def limit_up_market_sentiment(date: str | None = Query(default=None)) -> dict[str, Any]:
    return get_market_sentiment(date)


@limit_router.get("/industry-heat")
def limit_up_industry_heat(date: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return get_industry_heat(date)


@limit_strategy_router.post("/generate-signals")
def generate_limit_up_signals(date: str | None = Query(default=None)) -> dict[str, Any]:
    return get_limit_up_strategy_signals(trade_date=date)


@limit_strategy_router.get("/signals")
def limit_up_strategy_signals(
    date: str | None = Query(default=None),
    action_label: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    industry: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict[str, Any]:
    return get_limit_up_strategy_signals(
        trade_date=date,
        action_label=action_label,
        min_score=min_score,
        industry=industry,
        keyword=keyword,
    )
