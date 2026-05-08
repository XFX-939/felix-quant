from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.schemas.requests import BacktestPayload
from app.services.backtest_service import (
    delete_backtest_result,
    get_batch_backtest_detail,
    get_backtest_defaults,
    get_backtest_result,
    get_latest_backtest_result,
    list_backtest_results,
    run_backtest,
)
from app.services.limit_up_strategy_service import run_flum_backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run")
def post_backtest(payload: BacktestPayload) -> dict:
    try:
        return run_backtest(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/flum")
def post_flum_backtest(payload: dict[str, Any] = Body(default_factory=dict)) -> dict:
    return run_flum_backtest(payload)


@router.get("/results")
def get_backtest_results() -> list[dict]:
    return list_backtest_results()


@router.get("/defaults")
def get_defaults() -> dict:
    return get_backtest_defaults()


@router.get("/latest")
def get_latest_backtest() -> dict:
    result = get_latest_backtest_result()
    if not result:
        raise HTTPException(status_code=404, detail="backtest result not found")
    return result


@router.get("/history")
def get_history() -> list[dict]:
    return list_backtest_results(include_detail=False)


@router.get("/batch/{task_id}")
def get_batch_backtest_by_task(task_id: int) -> dict:
    result = get_batch_backtest_detail(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="batch backtest not found")
    return result


@router.get("/{result_id}")
def get_backtest_result_by_id(result_id: int) -> dict:
    result = get_backtest_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="backtest result not found")
    return result


@router.delete("/{result_id}")
def delete_backtest_result_by_id(result_id: int) -> dict:
    deleted = delete_backtest_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="backtest result not found")
    return {"deleted": True}


@router.get("/results/{result_id}")
def get_backtest_result_detail(result_id: int) -> dict:
    result = get_backtest_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="backtest result not found")
    return result
