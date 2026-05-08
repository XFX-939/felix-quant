from fastapi import APIRouter, HTTPException, Query

from app.services.strategy_service import get_signal, list_signals

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/today")
def get_today_signals() -> list[dict]:
    return list_signals(only_today=True)


@router.get("")
def get_signals(
    only_today: bool = False,
    search: str | None = None,
    industry: str | None = None,
    strategy_id: int | None = None,
    risk_level: str | None = None,
    suggested_action: str | None = None,
    limit: int | None = Query(default=20, ge=1, le=200),
) -> list[dict]:
    return list_signals(
        only_today=only_today,
        search=search,
        industry=industry,
        strategy_id=strategy_id,
        risk_level=risk_level,
        suggested_action=suggested_action,
        limit=limit,
    )


@router.get("/{signal_id}")
def get_signal_detail(signal_id: int) -> dict:
    signal = get_signal(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="signal not found")
    return signal
