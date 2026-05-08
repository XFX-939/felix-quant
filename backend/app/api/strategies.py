from fastapi import APIRouter, HTTPException

from app.schemas.requests import StrategyPayload
from app.services.strategy_source_service import get_strategy_source, list_strategy_sources, summarize_strategy_sources
from app.services.strategy_service import create_strategy, get_strategy, list_strategies, run_strategies, update_strategy

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
def get_strategies() -> list[dict]:
    return list_strategies()


@router.post("")
def post_strategy(payload: StrategyPayload) -> dict:
    return create_strategy(payload.model_dump())


@router.get("/sources")
def get_strategy_sources() -> list[dict]:
    return list_strategy_sources()


@router.get("/sources/summary")
def get_strategy_sources_summary() -> dict:
    return summarize_strategy_sources()


@router.get("/sources/{strategy_name}")
def get_strategy_source_detail(strategy_name: str) -> dict:
    return get_strategy_source(strategy_name)


@router.put("/{strategy_id}")
def put_strategy(strategy_id: int, payload: StrategyPayload) -> dict:
    strategy = update_strategy(strategy_id, payload.model_dump())
    if not strategy:
        raise HTTPException(status_code=404, detail="strategy not found")
    return strategy


@router.post("/{strategy_id}/run")
def run_strategy(strategy_id: int) -> dict:
    if not get_strategy(strategy_id):
        raise HTTPException(status_code=404, detail="strategy not found")
    return run_strategies(strategy_id=strategy_id)
