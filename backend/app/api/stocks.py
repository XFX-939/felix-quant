from fastapi import APIRouter, HTTPException, Query

from app.services.market_service import get_prices, get_stock, list_industries, list_stocks

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("")
def get_stocks(search: str | None = None, industry: str | None = None) -> list[dict]:
    return list_stocks(search=search, industry=industry)


@router.get("/industries")
def get_industries() -> list[str]:
    return list_industries()


@router.get("/{code}")
def get_stock_detail(code: str) -> dict:
    stock = get_stock(code)
    if not stock:
        raise HTTPException(status_code=404, detail="stock not found")
    return stock


@router.get("/{code}/prices")
def get_stock_prices(
    code: str,
    limit: int | None = Query(default=180, ge=1, le=1000),
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    return get_prices(code, limit=limit, start_date=start_date, end_date=end_date)

