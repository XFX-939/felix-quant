from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyPayload(BaseModel):
    name: str
    description: str = ""
    type: str = "多因子"
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class BacktestPayload(BaseModel):
    strategy_id: int
    stock_pool: str = "all"
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float = 100000
    fee_rate: float = 0.0003
    slippage: float = 0.0005
    rebalance_frequency: str = "daily"
    market_regime_filter: str | None = None
    stop_loss: float = 0.08
    take_profit: float | None = None
    position_cap: float = 0.2
    max_positions: int | None = None
    max_holding_days: int | None = None


class ReviewPayload(BaseModel):
    date: str
    stock_code: str
    signal_id: int | None = None
    action_taken: bool = False
    reason: str = ""
    result: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)


class RiskRulePayload(BaseModel):
    description: str | None = None
    threshold: float | None = None
    enabled: bool | None = None
