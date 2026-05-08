from fastapi import APIRouter

from app.db.database import dicts_from_rows, get_connection
from app.services.analytics import enrich_prices
from app.services.classic_quant import alpha_lab_catalog, market_regime_model, portfolio_risk_budget, research_integrity_check
from app.services.market_service import get_prices
from app.services.strategy_service import list_signals

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/market-regime")
def get_market_regime() -> dict:
    with get_connection() as conn:
        stocks = dicts_from_rows(
            conn.execute(
                """
                SELECT code, name, industry, market, list_date, is_st, is_suspended, float_market_cap
                FROM stocks
                ORDER BY code
                """
            ).fetchall()
        )
        trade_date = conn.execute("SELECT MAX(date) AS date FROM daily_prices").fetchone()["date"]
    frames = [{"stock": stock, "frame": enrich_prices(get_prices(stock["code"], limit=140))} for stock in stocks]
    return market_regime_model(frames, trade_date)


@router.get("/alpha-lab")
def get_alpha_lab() -> list[dict]:
    return alpha_lab_catalog()


@router.get("/integrity")
def get_research_integrity() -> dict:
    return research_integrity_check(
        {
            "stSuspensionDelistHandled": True,
            "transactionCost": True,
            "runTimestamp": True,
            "reproducibleTradeDate": True,
        }
    )


@router.get("/portfolio-risk-budget")
def get_portfolio_risk_budget() -> dict:
    regime = get_market_regime()["marketRegime"]
    candidates = [signal["strategyCandidate"] for signal in list_signals(only_today=True, limit=None) if signal.get("strategyCandidate")]
    return portfolio_risk_budget(candidates, regime)
