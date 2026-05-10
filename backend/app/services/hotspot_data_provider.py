from __future__ import annotations

from typing import Any


def get_market_snapshot(trade_date: str | None) -> dict[str, Any]:
    if trade_date == "2026-05-08":
        return {
            "tradeDate": trade_date,
            "provider": "manual_market_snapshot",
            "ready": True,
            "source": "public-close-reports-2026-05-08",
            "data": {
                "source": "public-close-reports-2026-05-08",
                "shIndexClose": 4179.95,
                "shIndexPctChg": 0.0,
                "szIndexClose": 15563.8,
                "szIndexPctChg": -0.5,
                "cybIndexClose": 3796.13,
                "cybIndexPctChg": -0.96,
                "kc50Close": 1640.46,
                "kc50PctChg": -2.29,
                "bse50Close": 1436.36,
                "bse50PctChg": 2.24,
                "totalAmount": 3080000000000,
                "totalAmountChange": -0.029,
                "upStockCount": 3634,
                "downStockCount": 1725,
                "flatStockCount": 148,
                "upStockRatio": 0.66,
                "limitUpCount": 112,
                "limitDownCount": 4,
                "strongSectorCount": 4,
                "topSectorAvgPct": 3.2,
                "growthStyleStrength": -0.96,
                "largeCapStrength": 0.0,
                "smallMidCapStrength": 0.8,
                "themes": [
                    {
                        "name": "商业航天",
                        "level": "行业降级",
                        "confidence": "中",
                        "themeScore": 84,
                        "relatedSectors": ["商业航天", "航天航空", "卫星互联网"],
                        "evidence": ["商业航天概念爆发，多只个股涨停", "市场热点快速轮动，中小盘题材相对活跃"],
                        "dataBasis": ["公开收评", "本地行情快照"],
                        "missingData": ["完整概念涨停池", "连板高度", "炸板率"],
                        "sectorPctChg": 3.2,
                        "sectorRank": 1,
                        "sectorLimitUpCount": 8,
                        "sectorStrongStockCount": 12,
                        "sectorAmountChange": 0.18,
                        "continuationDays": 1,
                    },
                    {
                        "name": "人形机器人",
                        "level": "行业降级",
                        "confidence": "中",
                        "themeScore": 80,
                        "relatedSectors": ["机器人", "通用设备", "汽车零部件"],
                        "evidence": ["机器人概念集体走强，多只个股封板", "黄白线分化，中小盘题材股表现较强"],
                        "dataBasis": ["公开收评", "本地行情快照"],
                        "missingData": ["完整概念涨停池", "连板高度", "炸板率"],
                        "sectorPctChg": 2.8,
                        "sectorRank": 2,
                        "sectorLimitUpCount": 7,
                        "sectorStrongStockCount": 10,
                        "sectorAmountChange": 0.14,
                        "continuationDays": 1,
                    },
                    {
                        "name": "PCB / CPO",
                        "level": "行业降级",
                        "confidence": "中",
                        "themeScore": 73,
                        "relatedSectors": ["PCB", "CPO", "光纤", "通信设备"],
                        "evidence": ["PCB、CPO、光纤概念盘中活跃", "通信设备方向保持局部强度"],
                        "dataBasis": ["公开收评", "本地行情快照"],
                        "missingData": ["完整概念涨停池", "连板高度", "炸板率"],
                        "sectorPctChg": 2.1,
                        "sectorRank": 3,
                        "sectorLimitUpCount": 4,
                        "sectorStrongStockCount": 8,
                        "sectorAmountChange": 0.1,
                        "continuationDays": 1,
                    },
                ],
            },
            "message": "使用 2026-05-08 公开收盘报道校准指数点位、涨跌幅、成交额、上涨家数和热点方向。",
        }
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
