from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from app.services.analytics import safe_float
from app.services.strategy_rules import parse_parameters

DRAGON_STRATEGY_DISPLAY_NAME = "短线龙头候选策略"
DRAGON_STRATEGY_CLASS_NAME = "DragonLeaderStrategy"

DRAGON_CONFIG = {
    "minListDays": 60,
    "minClosePrice": 3,
    "maxClosePrice": 80,
    "minAmount": 200000000,
    "minFloatMarketCap": 2000000000,
    "maxFloatMarketCap": 30000000000,
    "minScore": 60,
}

DEFAULT_EXIT_RULES = [
    "次日低开超过 -5%，且 30 分钟内不能翻红，退出观察",
    "跌破 5 日均线，退出观察",
    "跌破前一日涨停价关键支撑，退出观察",
    "高开低走且放量，降级为高风险",
    "所在板块涨停数量明显下降，退出观察",
    "市场情绪从 Hot/Neutral 转为 Cold，全部短线候选降级",
]


@dataclass
class DragonDiagnostics:
    base_filter_passed: bool = False
    hit_limit_or_breakout: bool = False
    hit_sector_linkage: bool = False
    final_candidate: bool = False
    high_risk_candidate: bool = False
    filtered_reason: str = ""


def is_dragon_strategy(strategy: dict | None) -> bool:
    if not strategy:
        return False
    params = parse_parameters(strategy.get("parameters"))
    name = str(strategy.get("name", ""))
    return (
        DRAGON_STRATEGY_CLASS_NAME in name
        or DRAGON_STRATEGY_DISPLAY_NAME in name
        or params.get("strategy_class") == DRAGON_STRATEGY_CLASS_NAME
    )


def merged_config(strategy: dict | None = None) -> dict[str, float]:
    params = parse_parameters(strategy.get("parameters") if strategy else None)
    raw = params.get("dragon_config") if isinstance(params.get("dragon_config"), dict) else params
    config = dict(DRAGON_CONFIG)
    for key, value in raw.items():
        if key in config:
            config[key] = value
    return config


def is_limit_up(stock: dict | pd.Series) -> bool:
    pct_chg = _get_number(stock, "pctChg", "pct_change")
    return pct_chg >= _limit_threshold(stock)


def is_limit_down(stock: dict | pd.Series) -> bool:
    pct_chg = _get_number(stock, "pctChg", "pct_change")
    return pct_chg <= -_limit_threshold(stock)


def is_strong_breakout(stock: dict | pd.Series) -> bool:
    pct_chg = _get_number(stock, "pctChg", "pct_change")
    close = _get_number(stock, "close")
    ma20 = _get_number(stock, "ma20")
    high20 = _get_number(stock, "high20")
    volume_ratio = _get_number(stock, "volumeRatio", "volume_ratio")
    return pct_chg >= 6 and close > ma20 and close >= high20 * 0.98 and volume_ratio >= 1.8


def prepare_dragon_context(stock_frames: list[dict], trade_date: str) -> dict[str, Any]:
    rows: list[dict] = []
    yesterday_limit_returns: list[float] = []
    for item in stock_frames:
        stock = item["stock"]
        frame = item["frame"]
        idx = _index_for_date(frame, trade_date)
        if idx is None:
            continue
        row = _row_payload(stock, frame, idx)
        row["consecutiveLimitUpDays"] = _consecutive_limit_up_days(stock, frame, idx)
        rows.append(row)
        if idx > 0:
            yesterday = _row_payload(stock, frame, idx - 1)
            if is_limit_up(yesterday):
                yesterday_limit_returns.append(safe_float(row.get("pct_change")))

    total = len(rows)
    market_limit_up_count = sum(1 for row in rows if is_limit_up(row))
    market_limit_down_count = sum(1 for row in rows if is_limit_down(row))
    up_stock_ratio = sum(1 for row in rows if safe_float(row.get("pct_change")) > 0) / total if total else 0
    high_board_height = max((int(row.get("consecutiveLimitUpDays", 0)) for row in rows), default=0)
    yesterday_limit_avg = sum(yesterday_limit_returns) / len(yesterday_limit_returns) if yesterday_limit_returns else 0
    index_pct_chg = sum(safe_float(row.get("pct_change")) for row in rows) / total if total else 0
    index_return_5d = sum(safe_float(row.get("ret5")) * 100 for row in rows) / total if total else 0
    index_return_20d = sum(safe_float(row.get("ret20")) * 100 for row in rows) / total if total else 0

    sector_rows: dict[str, list[dict]] = {}
    for row in rows:
        sector_rows.setdefault(str(row.get("industry") or "未分类"), []).append(row)
    sector_stats: dict[str, dict] = {}
    ranked = sorted(
        (
            (
                sector,
                sum(safe_float(row.get("pct_change")) for row in values) / len(values),
                values,
            )
            for sector, values in sector_rows.items()
            if values
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    for rank, (sector, avg_pct, values) in enumerate(ranked, start=1):
        sector_stats[sector] = {
            "sectorName": sector,
            "sectorLimitUpCount": sum(1 for row in values if is_limit_up(row)),
            "sectorAvgPct": round(avg_pct, 2),
            "sectorTopPct": round(max(safe_float(row.get("pct_change")) for row in values), 2),
            "sectorStrengthRank": rank,
        }

    sentiment = _market_sentiment(
        market_limit_up_count,
        market_limit_down_count,
        up_stock_ratio,
        yesterday_limit_avg,
        total,
    )
    return {
        "tradeDate": trade_date,
        "marketLimitUpCount": market_limit_up_count,
        "marketLimitDownCount": market_limit_down_count,
        "upStockRatio": up_stock_ratio,
        "highBoardHeight": high_board_height,
        "yesterdayLimitUpAvgReturn": round(yesterday_limit_avg, 2),
        "indexPctChg": round(index_pct_chg, 2),
        "indexReturn5d": round(index_return_5d, 2),
        "indexReturn20d": round(index_return_20d, 2),
        "marketSentiment": sentiment,
        "sectorStats": sector_stats,
    }


def evaluate_dragon_leader(
    strategy: dict,
    stock: dict,
    enriched: pd.DataFrame,
    context: dict[str, Any],
    row_index: int | None = None,
) -> tuple[dict | None, DragonDiagnostics]:
    diagnostics = DragonDiagnostics()
    if enriched.empty or len(enriched) < int(merged_config(strategy)["minListDays"]):
        diagnostics.filtered_reason = "上市交易样本不足"
        return None, diagnostics

    idx = row_index if row_index is not None else len(enriched) - 1
    if idx < 0 or idx >= len(enriched):
        diagnostics.filtered_reason = "交易日数据缺失"
        return None, diagnostics
    row = _row_payload(stock, enriched, idx)
    config = merged_config(strategy)
    basic_reason = _basic_filter_reason(stock, row, idx + 1, config)
    if basic_reason:
        diagnostics.filtered_reason = basic_reason
        return None, diagnostics
    diagnostics.base_filter_passed = True

    volume_ratio = _volume_ratio(row)
    amount_ratio = _amount_ratio(row)
    turnover_rate = _turnover_rate(stock, row)
    row["volumeRatio"] = volume_ratio
    row["amountRatio"] = amount_ratio
    row["turnoverRate"] = turnover_rate

    limit_up = is_limit_up(row)
    strong_breakout = is_strong_breakout(row)
    if not limit_up and not strong_breakout:
        diagnostics.filtered_reason = "未触发涨停或强势突破"
        return None, diagnostics
    diagnostics.hit_limit_or_breakout = True

    sector_name = str(stock.get("industry") or "未分类")
    sector = context["sectorStats"].get(
        sector_name,
        {
            "sectorName": sector_name,
            "sectorLimitUpCount": 0,
            "sectorAvgPct": 0,
            "sectorTopPct": 0,
            "sectorStrengthRank": 999,
        },
    )
    diagnostics.hit_sector_linkage = (
        sector["sectorLimitUpCount"] >= 2
        or sector["sectorAvgPct"] >= 3
        or sector["sectorStrengthRank"] <= 10
    )

    consecutive_limit_days = _consecutive_limit_up_days(stock, enriched, idx)
    board_height_score = _board_height_score(consecutive_limit_days)
    sector_score = _sector_score(sector)
    pct_chg = safe_float(row.get("pct_change"))
    stock_return_5d = safe_float(row.get("ret5")) * 100
    stock_return_20d = safe_float(row.get("ret20")) * 100
    stock_excess_market = pct_chg - safe_float(context.get("indexPctChg"))
    stock_excess_sector = pct_chg - safe_float(sector.get("sectorAvgPct"))
    relative_strength_5d = stock_return_5d - safe_float(context.get("indexReturn5d"))
    relative_strength_20d = stock_return_20d - safe_float(context.get("indexReturn20d"))
    relative_strength_score = (
        10 * clamp(stock_excess_market / 8)
        + 10 * clamp(stock_excess_sector / 5)
        + 10 * clamp(relative_strength_5d / 15)
    )
    volume_turnover_score = _volume_score(volume_ratio) + _turnover_score(turnover_rate)
    seal_quality = _seal_quality_score(limit_up)
    limit_up_score = 30 if limit_up else 18 if strong_breakout else 0

    risk_penalty, risk_reasons, severe_risk = _risk_penalty(
        stock,
        row,
        enriched,
        idx,
        consecutive_limit_days,
        sector,
        context["marketSentiment"],
        turnover_rate,
        volume_ratio,
        limit_up,
    )
    relative_strength_ok = stock_excess_market > 3 and relative_strength_5d > 5
    weak_sector = sector["sectorLimitUpCount"] < 2 and sector["sectorAvgPct"] < 3 and sector["sectorStrengthRank"] > 10
    if not relative_strength_ok:
        risk_penalty += 8
        risk_reasons.append("相对强度未达到短线龙头候选最低要求，需降级观察")
    if weak_sector:
        risk_penalty += 6
        risk_reasons.append("板块强度不足，候选等级下调")

    raw_score = (
        0.30 * limit_up_score
        + 0.25 * board_height_score
        + 0.20 * sector_score
        + 0.15 * relative_strength_score
        + 0.10 * volume_turnover_score
    )
    dragon_score = raw_score / 25 * 100 - risk_penalty
    dragon_score = round(max(0, min(100, dragon_score)), 2)
    if dragon_score < float(config["minScore"]):
        diagnostics.filtered_reason = f"dragonScore {dragon_score:.1f} 低于阈值"
        return None, diagnostics

    candidate_level = _candidate_level(dragon_score)
    downgrade_steps = 0
    if weak_sector:
        downgrade_steps += 1
    if not relative_strength_ok:
        downgrade_steps += 1
    if context["marketSentiment"] == "Cold":
        downgrade_steps += 1
    candidate_level = _downgrade_level(candidate_level, downgrade_steps)

    risk_level_en, risk_level_cn = _risk_level(risk_penalty, severe_risk)
    suggested_action = _suggested_action(dragon_score, risk_level_cn, context["marketSentiment"])
    trigger_reasons = _trigger_reasons(
        limit_up,
        strong_breakout,
        consecutive_limit_days,
        sector,
        relative_strength_5d,
        volume_ratio,
        row,
    )
    if not risk_reasons:
        risk_reasons.append("未触发主要短线风险，仍需人工确认")

    diagnostics.final_candidate = True
    diagnostics.high_risk_candidate = risk_level_cn == "高"
    metadata = {
        "strategyClass": DRAGON_STRATEGY_CLASS_NAME,
        "strategyName": DRAGON_STRATEGY_DISPLAY_NAME,
        "code": stock["code"],
        "name": stock["name"],
        "tradeDate": str(row["date"].date().isoformat() if hasattr(row["date"], "date") else row["date"]),
        "close": round(safe_float(row.get("close")), 2),
        "pctChg": round(pct_chg, 2),
        "amount": round(safe_float(row.get("amount")), 2),
        "turnoverRate": round(turnover_rate, 2),
        "volumeRatio": round(volume_ratio, 2),
        "amountRatio": round(amount_ratio, 2),
        "isLimitUp": limit_up,
        "consecutiveLimitUpDays": consecutive_limit_days,
        "isStrongBreakout": strong_breakout,
        "sectorName": sector_name,
        "sectorLimitUpCount": int(sector["sectorLimitUpCount"]),
        "sectorAvgPct": round(safe_float(sector["sectorAvgPct"]), 2),
        "sectorTopPct": round(safe_float(sector["sectorTopPct"]), 2),
        "sectorStrengthRank": int(sector["sectorStrengthRank"]),
        "stockExcessMarket": round(stock_excess_market, 2),
        "stockExcessSector": round(stock_excess_sector, 2),
        "relativeStrength5d": round(relative_strength_5d, 2),
        "relativeStrength20d": round(relative_strength_20d, 2),
        "dragonScore": dragon_score,
        "candidateLevel": candidate_level,
        "marketSentiment": context["marketSentiment"],
        "riskLevel": risk_level_cn,
        "riskPenalty": round(risk_penalty, 2),
        "suggestedAction": suggested_action,
        "triggerReasons": trigger_reasons,
        "riskReasons": risk_reasons,
        "exitRules": DEFAULT_EXIT_RULES,
        "marketLimitUpCount": int(context["marketLimitUpCount"]),
        "marketLimitDownCount": int(context["marketLimitDownCount"]),
        "highBoardHeight": int(context["highBoardHeight"]),
    }
    return (
        {
            "signal_type": "dragon_leader_candidate",
            "score": dragon_score,
            "reason": "；".join(trigger_reasons),
            "risk_reason": "；".join(risk_reasons),
            "risk_level": risk_level_en,
            "metadata": metadata,
        },
        diagnostics,
    )


def evaluate_dragon_observation_candidate(
    strategy: dict,
    stock: dict,
    enriched: pd.DataFrame,
    context: dict[str, Any],
    row_index: int | None = None,
) -> tuple[dict | None, DragonDiagnostics]:
    diagnostics = DragonDiagnostics()
    config = merged_config(strategy)
    if enriched.empty or len(enriched) < int(config["minListDays"]):
        diagnostics.filtered_reason = "上市交易样本不足"
        return None, diagnostics

    idx = row_index if row_index is not None else len(enriched) - 1
    if idx < 0 or idx >= len(enriched):
        diagnostics.filtered_reason = "交易日数据缺失"
        return None, diagnostics
    row = _row_payload(stock, enriched, idx)
    basic_reason = _basic_filter_reason(stock, row, idx + 1, config)
    if basic_reason:
        diagnostics.filtered_reason = basic_reason
        return None, diagnostics
    diagnostics.base_filter_passed = True

    volume_ratio = _volume_ratio(row)
    amount_ratio = _amount_ratio(row)
    turnover_rate = _turnover_rate(stock, row)
    row["volumeRatio"] = volume_ratio
    row["amountRatio"] = amount_ratio
    row["turnoverRate"] = turnover_rate

    limit_up = is_limit_up(row)
    strong_breakout = is_strong_breakout(row)
    diagnostics.hit_limit_or_breakout = limit_up or strong_breakout

    sector_name = str(stock.get("industry") or "未分类")
    sector = context.get("sectorStats", {}).get(
        sector_name,
        {
            "sectorName": sector_name,
            "sectorLimitUpCount": 0,
            "sectorAvgPct": 0,
            "sectorTopPct": 0,
            "sectorStrengthRank": 999,
        },
    )
    diagnostics.hit_sector_linkage = (
        int(sector.get("sectorLimitUpCount", 0)) >= 2
        or safe_float(sector.get("sectorAvgPct")) >= 3
        or int(sector.get("sectorStrengthRank", 999)) <= 10
    )

    pct_chg = safe_float(row.get("pct_change"))
    stock_return_5d = safe_float(row.get("ret5")) * 100
    stock_return_20d = safe_float(row.get("ret20")) * 100
    stock_excess_market = pct_chg - safe_float(context.get("indexPctChg"))
    stock_excess_sector = pct_chg - safe_float(sector.get("sectorAvgPct"))
    relative_strength_5d = stock_return_5d - safe_float(context.get("indexReturn5d"))
    relative_strength_20d = stock_return_20d - safe_float(context.get("indexReturn20d"))
    consecutive_limit_days = _consecutive_limit_up_days(stock, enriched, idx)
    relative_strength_score = (
        10 * clamp(stock_excess_market / 8)
        + 10 * clamp(stock_excess_sector / 5)
        + 10 * clamp(relative_strength_5d / 15)
    )
    risk_penalty, risk_reasons, severe_risk = _risk_penalty(
        stock,
        row,
        enriched,
        idx,
        consecutive_limit_days,
        sector,
        str(context.get("marketSentiment") or "Cold"),
        turnover_rate,
        volume_ratio,
        limit_up,
    )
    if not limit_up and not strong_breakout:
        risk_reasons.append("未触发涨停或强势突破，仅作为短线强度观察，需人工确认")

    trend_gap = safe_float(row.get("close")) / max(safe_float(row.get("ma20")), 1) - 1
    near_high_gap = safe_float(row.get("close")) / max(safe_float(row.get("high20")), 1) - 0.92
    relevance_score = (
        45
        + 25 * clamp(stock_excess_market / 8)
        + 20 * clamp(relative_strength_5d / 15)
        + 10 * clamp(relative_strength_20d / 25)
        + 15 * clamp(pct_chg / 6)
        + 10 * clamp((volume_ratio - 1) / 2)
        + 10 * clamp(trend_gap / 0.08)
        + 5 * clamp(near_high_gap / 0.08)
        + 5 * clamp(safe_float(sector.get("sectorAvgPct")) / 4)
        - risk_penalty * 0.35
    )
    observation_threshold = float(config.get("observationMinScore", 45))
    if relevance_score < observation_threshold:
        diagnostics.filtered_reason = f"观察相关性 {relevance_score:.1f} 低于阈值"
        return None, diagnostics

    dragon_score = round(max(60, min(69.9, relevance_score)), 2)
    risk_level_en, risk_level_cn = _risk_level(risk_penalty, severe_risk)
    if risk_level_en == "low":
        risk_level_en, risk_level_cn = "medium", "中"
    suggested_action = _suggested_action(dragon_score, risk_level_cn, str(context.get("marketSentiment") or "Cold"))
    if suggested_action == "谨慎观察":
        suggested_action = "观察"
    trigger_reasons = _observation_trigger_reasons(
        pct_chg,
        relative_strength_5d,
        relative_strength_20d,
        volume_ratio,
        sector,
        row,
    )

    diagnostics.final_candidate = True
    diagnostics.high_risk_candidate = risk_level_cn == "高"
    metadata = {
        "strategyClass": DRAGON_STRATEGY_CLASS_NAME,
        "strategyName": DRAGON_STRATEGY_DISPLAY_NAME,
        "candidateMode": "ranked_observation",
        "strictPassed": False,
        "code": stock["code"],
        "name": stock["name"],
        "tradeDate": str(row["date"].date().isoformat() if hasattr(row["date"], "date") else row["date"]),
        "close": round(safe_float(row.get("close")), 2),
        "pctChg": round(pct_chg, 2),
        "amount": round(safe_float(row.get("amount")), 2),
        "turnoverRate": round(turnover_rate, 2),
        "volumeRatio": round(volume_ratio, 2),
        "amountRatio": round(amount_ratio, 2),
        "isLimitUp": limit_up,
        "consecutiveLimitUpDays": consecutive_limit_days,
        "isStrongBreakout": strong_breakout,
        "sectorName": sector_name,
        "sectorLimitUpCount": int(sector.get("sectorLimitUpCount", 0)),
        "sectorAvgPct": round(safe_float(sector.get("sectorAvgPct")), 2),
        "sectorTopPct": round(safe_float(sector.get("sectorTopPct")), 2),
        "sectorStrengthRank": int(sector.get("sectorStrengthRank", 999)),
        "stockExcessMarket": round(stock_excess_market, 2),
        "stockExcessSector": round(stock_excess_sector, 2),
        "relativeStrength5d": round(relative_strength_5d, 2),
        "relativeStrength20d": round(relative_strength_20d, 2),
        "dragonScore": dragon_score,
        "candidateLevel": "观察候选",
        "marketSentiment": str(context.get("marketSentiment") or "Cold"),
        "riskLevel": risk_level_cn,
        "riskPenalty": round(risk_penalty, 2),
        "suggestedAction": suggested_action,
        "triggerReasons": trigger_reasons,
        "riskReasons": risk_reasons,
        "exitRules": DEFAULT_EXIT_RULES,
        "marketLimitUpCount": int(context.get("marketLimitUpCount", 0)),
        "marketLimitDownCount": int(context.get("marketLimitDownCount", 0)),
        "highBoardHeight": int(context.get("highBoardHeight", 0)),
    }
    return (
        {
            "signal_type": "dragon_leader_observation",
            "score": dragon_score,
            "reason": "；".join(trigger_reasons),
            "risk_reason": "；".join(risk_reasons),
            "risk_level": risk_level_en,
            "metadata": metadata,
        },
        diagnostics,
    )


def _row_payload(stock: dict, frame: pd.DataFrame, idx: int) -> dict[str, Any]:
    row = frame.iloc[idx].to_dict()
    row["code"] = stock.get("code")
    row["name"] = stock.get("name")
    row["industry"] = stock.get("industry")
    row["market"] = stock.get("market")
    row["is_st"] = stock.get("is_st", 0)
    return row


def _index_for_date(frame: pd.DataFrame, trade_date: str) -> int | None:
    if frame.empty:
        return None
    dates = frame["date"].dt.date.astype(str)
    matches = dates[dates == trade_date]
    if matches.empty:
        return None
    return int(matches.index[-1])


def _limit_threshold(stock: dict | pd.Series) -> float:
    name = str(_get_value(stock, "name") or "")
    code = str(_get_value(stock, "code") or "")
    market = str(_get_value(stock, "market") or "").upper()
    is_st = bool(_get_value(stock, "is_st")) or "ST" in name.upper()
    if is_st:
        return 4.8
    if code.startswith(("300", "301", "688")):
        return 19.0
    if market in {"BJ", "BSE"} or code.startswith(("8", "4", "43", "87")):
        return 29.0
    return 9.7


def _basic_filter_reason(stock: dict, row: dict, list_days: int, config: dict[str, float]) -> str:
    name = str(stock.get("name") or "")
    close = safe_float(row.get("close"))
    amount = safe_float(row.get("amount"))
    float_cap = safe_float(stock.get("float_market_cap"))
    if "ST" in name.upper() or "退" in name:
        return "ST、退市整理或风险警示股票被过滤"
    if bool(stock.get("is_suspended")):
        return "停牌股票被过滤"
    if list_days < int(config["minListDays"]):
        return "上市不足 60 个交易日"
    if close < float(config["minClosePrice"]) or close > float(config["maxClosePrice"]):
        return "收盘价不在短线策略价格区间"
    if amount < float(config["minAmount"]):
        return "当日成交额低于短线策略阈值"
    if float_cap < float(config["minFloatMarketCap"]) or float_cap > float(config["maxFloatMarketCap"]):
        return "流通市值不在短线策略区间"
    return ""


def _consecutive_limit_up_days(stock: dict, frame: pd.DataFrame, idx: int) -> int:
    count = 0
    for cursor in range(idx, -1, -1):
        row = _row_payload(stock, frame, cursor)
        if not is_limit_up(row):
            break
        count += 1
    return count


def _board_height_score(days: int) -> int:
    if days <= 0:
        return 0
    if days == 1:
        return 10
    if days == 2:
        return 22
    if days == 3:
        return 30
    if days == 4:
        return 25
    return 15


def _sector_score(sector: dict) -> float:
    return (
        10 * clamp(safe_float(sector.get("sectorLimitUpCount")) / 5)
        + 10 * clamp(safe_float(sector.get("sectorAvgPct")) / 5)
        + 10 * (1 if int(sector.get("sectorStrengthRank", 999)) <= 10 else 0)
    )


def _volume_ratio(row: dict) -> float:
    return safe_float(row.get("volume")) / max(safe_float(row.get("volume_ma5")), 1)


def _amount_ratio(row: dict) -> float:
    return safe_float(row.get("amount")) / max(safe_float(row.get("amount_ma5")), 1)


def _turnover_rate(stock: dict, row: dict) -> float:
    float_cap = safe_float(stock.get("float_market_cap"))
    if float_cap <= 0:
        return 0
    return safe_float(row.get("amount")) / float_cap * 100


def _volume_score(volume_ratio: float) -> int:
    if 1.5 <= volume_ratio <= 3:
        return 10
    if 3 < volume_ratio <= 5:
        return 8
    if 5 < volume_ratio <= 8:
        return 4
    return 0


def _turnover_score(turnover_rate: float) -> int:
    if 5 <= turnover_rate <= 18:
        return 10
    if 18 < turnover_rate <= 25:
        return 7
    if 25 < turnover_rate <= 35:
        return 3
    return 0


def _seal_quality_score(limit_up: bool) -> int:
    return 6 if limit_up else 0


def _risk_penalty(
    stock: dict,
    row: dict,
    frame: pd.DataFrame,
    idx: int,
    consecutive_limit_days: int,
    sector: dict,
    market_sentiment: str,
    turnover_rate: float,
    volume_ratio: float,
    close_on_limit: bool,
) -> tuple[float, list[str], bool]:
    penalty = 0.0
    reasons: list[str] = []
    severe = False
    one_word_days = _consecutive_one_word_limit_days(stock, frame, idx)
    if one_word_days >= 2:
        penalty += 30
        severe = True
        reasons.append("连续一字板，流动性和接力风险高")
    if _is_day_extreme_reversal(stock, row):
        penalty += 40
        severe = True
        reasons.append("出现天地板，短线情绪剧烈退潮")
    if _touched_limit_but_not_closed(stock, row, close_on_limit):
        penalty += 30
        severe = True
        reasons.append("炸板未回封，资金承接不足")
    if safe_float(row.get("ret5")) > 0.5:
        penalty += 15
        reasons.append("近 5 日涨幅过高，追高风险增加")
    if safe_float(row.get("ret10")) > 0.8:
        penalty += 25
        severe = True
        reasons.append("近 10 日涨幅过高，存在高位分歧风险")
    if turnover_rate > 35:
        penalty += 20
        severe = True
        reasons.append("换手率过高，筹码分歧剧烈")
    if volume_ratio > 8:
        penalty += 20
        reasons.append("成交量极端放大，可能存在放量出货风险")
    if int(sector.get("sectorLimitUpCount", 0)) < 2:
        penalty += 10
        reasons.append("板块联动不足，可能是一日游行情")
    if market_sentiment == "Cold":
        penalty += 20
        reasons.append("市场情绪偏冷，短线接力失败概率升高")
    return penalty, reasons, severe


def _consecutive_one_word_limit_days(stock: dict, frame: pd.DataFrame, idx: int) -> int:
    count = 0
    for cursor in range(idx, -1, -1):
        row = _row_payload(stock, frame, cursor)
        close = safe_float(row.get("close"))
        if not is_limit_up(row):
            break
        if abs(safe_float(row.get("open")) - close) <= 0.01 and abs(safe_float(row.get("high")) - close) <= 0.01 and abs(safe_float(row.get("low")) - close) <= 0.01:
            count += 1
        else:
            break
    return count


def _is_day_extreme_reversal(stock: dict, row: dict) -> bool:
    threshold = _limit_threshold({**row, **stock})
    previous_close = safe_float(row.get("close")) / (1 + safe_float(row.get("pct_change")) / 100) if safe_float(row.get("pct_change")) > -99 else 0
    if previous_close <= 0:
        return False
    high_pct = (safe_float(row.get("high")) / previous_close - 1) * 100
    low_pct = (safe_float(row.get("low")) / previous_close - 1) * 100
    return high_pct >= threshold and low_pct <= -threshold * 0.85


def _touched_limit_but_not_closed(stock: dict, row: dict, close_on_limit: bool) -> bool:
    previous_close = safe_float(row.get("close")) / (1 + safe_float(row.get("pct_change")) / 100) if safe_float(row.get("pct_change")) > -99 else 0
    if previous_close <= 0:
        return False
    high_pct = (safe_float(row.get("high")) / previous_close - 1) * 100
    return high_pct >= _limit_threshold({**row, **stock}) and not close_on_limit


def _risk_level(risk_penalty: float, severe: bool) -> tuple[str, str]:
    if risk_penalty >= 30 or severe:
        return "high", "高"
    if risk_penalty >= 15:
        return "medium", "中"
    return "low", "低"


def _candidate_level(score: float) -> str:
    if score >= 80:
        return "核心龙头候选"
    if score >= 70:
        return "强势龙头候选"
    return "观察候选"


def _downgrade_level(level: str, steps: int) -> str:
    levels = ["观察候选", "强势龙头候选", "核心龙头候选"]
    index = levels.index(level)
    return levels[max(0, index - steps)]


def _suggested_action(score: float, risk_level: str, market_sentiment: str) -> str:
    if risk_level == "高":
        return "暂不参与"
    if market_sentiment == "Cold":
        return "观察"
    if score >= 80:
        return "谨慎观察"
    if score >= 60:
        return "观察"
    return "暂不参与"


def _trigger_reasons(
    limit_up: bool,
    strong_breakout: bool,
    consecutive_limit_days: int,
    sector: dict,
    relative_strength_5d: float,
    volume_ratio: float,
    row: dict,
) -> list[str]:
    reasons: list[str] = []
    if limit_up:
        reasons.append("今日涨停，短线资金关注度高")
    elif strong_breakout:
        reasons.append("强势突破 20 日区间，短线资金关注度提升")
    if consecutive_limit_days >= 1:
        reasons.append(f"连续 {consecutive_limit_days} 板，具备龙头候选辨识度")
    if int(sector.get("sectorLimitUpCount", 0)) >= 2:
        reasons.append(f"所在板块涨停数量达到 {int(sector['sectorLimitUpCount'])} 只，板块联动较强")
    reasons.append(f"个股 5 日相对大盘超额收益为 {relative_strength_5d:.1f}%，强于市场")
    reasons.append(f"成交量为 5 日均量 {volume_ratio:.1f} 倍，资金参与度提升")
    if safe_float(row.get("close")) >= safe_float(row.get("high20")) * 0.98:
        reasons.append("收盘价接近 20 日新高，趋势强势")
    return reasons


def _observation_trigger_reasons(
    pct_chg: float,
    relative_strength_5d: float,
    relative_strength_20d: float,
    volume_ratio: float,
    sector: dict,
    row: dict,
) -> list[str]:
    reasons = ["未触发涨停或强势突破，按短线相对强度进入观察池"]
    if pct_chg > 0:
        reasons.append(f"今日涨幅 {pct_chg:.2f}%，短线表现强于弱势标的")
    if relative_strength_5d > 0:
        reasons.append(f"个股 5 日相对大盘超额收益为 {relative_strength_5d:.1f}%，相对强度靠前")
    if relative_strength_20d > 0:
        reasons.append(f"个股 20 日相对大盘超额收益为 {relative_strength_20d:.1f}%，中短期韧性较好")
    if volume_ratio > 1:
        reasons.append(f"成交量为 5 日均量 {volume_ratio:.1f} 倍，资金参与度提升")
    if int(sector.get("sectorStrengthRank", 999)) <= 10:
        reasons.append(f"所在行业强度排名第 {int(sector['sectorStrengthRank'])}，板块相对靠前")
    if safe_float(row.get("close")) > safe_float(row.get("ma20")):
        reasons.append("收盘价位于 MA20 上方，短线趋势保持观察价值")
    return reasons[:6]


def _market_sentiment(limit_up_count: int, limit_down_count: int, up_ratio: float, yesterday_limit_return: float, sample_size: int) -> str:
    scale = 1 if sample_size >= 100 else max(1, 5000 / max(sample_size, 1))
    effective_limit_up = limit_up_count * scale
    effective_limit_down = limit_down_count * scale
    if yesterday_limit_return < -1:
        return "Cold"
    if effective_limit_up >= 60 and effective_limit_down <= 10 and up_ratio >= 0.6 and yesterday_limit_return > 1:
        return "Hot"
    if effective_limit_up >= 30 and effective_limit_down <= 20 and up_ratio >= 0.45:
        return "Neutral"
    return "Cold"


def _get_number(stock: dict | pd.Series, *keys: str) -> float:
    for key in keys:
        value = _get_value(stock, key)
        if value is not None:
            return safe_float(value)
    return 0


def _get_value(stock: dict | pd.Series, key: str) -> Any:
    if isinstance(stock, pd.Series):
        return stock.get(key)
    return stock.get(key)


def clamp(value: float, low: float = 0, high: float = 1) -> float:
    return max(low, min(high, value))


def list_days_from_stock(stock: dict) -> int:
    list_date = stock.get("list_date")
    if not list_date:
        return 999
    try:
        return (datetime.now().date() - datetime.fromisoformat(str(list_date)).date()).days
    except ValueError:
        return 999
