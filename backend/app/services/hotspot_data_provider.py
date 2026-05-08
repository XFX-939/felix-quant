from __future__ import annotations

from typing import Any


def get_market_snapshot(trade_date: str | None) -> dict[str, Any]:
    if trade_date == "2026-05-06":
        return {
            "tradeDate": trade_date,
            "provider": "manual_market_snapshot",
            "ready": True,
            "source": "user-reported-2026-05-06",
            "data": {
                "source": "user-reported-2026-05-06",
                "shIndexPctChg": 1.17,
                "szIndexPctChg": 2.33,
                "cybIndexPctChg": 2.75,
                "kc50PctChg": 5.47,
                "totalAmount": 3250000000000,
                "totalAmountChange": 0.22,
                "upStockCount": 3900,
                "downStockCount": 1200,
                "upStockRatio": 0.75,
                "limitUpCount": 118,
                "limitDownCount": 6,
                "strongSectorCount": 6,
                "topSectorAvgPct": 5.2,
                "growthStyleStrength": 4.1,
                "largeCapStrength": 1.2,
                "smallMidCapStrength": 3.1,
            },
            "message": "使用 2026-05-06 全市场行情快照修正本地样本股票池的市场状态判断。",
        }
    return _not_ready(
        trade_date,
        "market_snapshot",
        "全市场指数、成交额、涨跌停和上涨家数快照尚未接入，当前使用本地股票池降级估算。",
    )


def get_limit_up_list(trade_date: str | None) -> dict[str, Any]:
    return _not_ready(
        trade_date,
        "limit_up_list",
        "涨停池、跌停池、炸板池尚未接入，当前热点策略使用行业行情降级估算。",
    )


def get_limit_board_list(trade_date: str | None) -> dict[str, Any]:
    return _not_ready(
        trade_date,
        "limit_board_list",
        "连板池、连板高度和连板家数尚未接入，当前龙头辨识度使用近似规则。",
    )


def get_hot_concept_list(trade_date: str | None) -> dict[str, Any]:
    return _not_ready(
        trade_date,
        "hot_concept_list",
        "最强概念板块、板块热点排名和题材成分股尚未接入，今日主线不输出强判断。",
    )


def get_sector_strength(trade_date: str | None) -> dict[str, Any]:
    return _not_ready(
        trade_date,
        "sector_strength",
        "行业涨幅排名和行业成交额变化由本地样本估算，需接入全市场行业强度数据。",
    )


def _not_ready(trade_date: str | None, name: str, message: str) -> dict[str, Any]:
    return {
        "tradeDate": trade_date,
        "provider": name,
        "ready": False,
        "source": "local-fallback",
        "data": [],
        "message": message,
    }
