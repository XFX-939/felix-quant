from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import backtest, dashboard, data, market_data, research, reviews, risk, signals, stock_inspector, stocks, strategies, strategy_performance, sync, tasks
from app.core.config import APP_NAME, CORS_ORIGIN_REGEX, CORS_ORIGINS, DISCLAIMER
from app.db.database import initialize_database
from app.services.strategy_service import list_signals, run_strategies


app = FastAPI(title=APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    if not list_signals(only_today=True):
        run_strategies()


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}


app.include_router(dashboard.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(market_data.router, prefix="/api")
app.include_router(market_data.limit_router, prefix="/api")
app.include_router(market_data.limit_strategy_router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(strategy_performance.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(stock_inspector.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
