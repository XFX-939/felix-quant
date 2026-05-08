from fastapi import APIRouter, HTTPException, Query

from app.services.stock_inspector_service import get_stock_inspection_report

router = APIRouter(prefix="/stock-inspector", tags=["stock-inspector"])


@router.get("/{code}")
def inspect_stock(
    code: str,
    trade_date: str | None = Query(default=None),
    force: bool = Query(default=False),
) -> dict:
    try:
        return get_stock_inspection_report(code, trade_date=trade_date, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
