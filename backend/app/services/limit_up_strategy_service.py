from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

import numpy as np

from app.db.database import dicts_from_rows, get_connection, now_iso
from app.services.market_data_service import get_limit_up_stats, target_trade_date

STRATEGY_NAME = "Felix 连板情绪强度策略"
STRATEGY_NAME_EN = "Felix Limit-Up Momentum Strategy"
STRATEGY_CODE = "FLUM"
DISCLAIMER = "仓位建议仅用于策略回测和交易计划，不构成投资建议。"

INDUSTRY_KEYWORDS: list[tuple[str, str, str]] = [
    ("银行", "银行", "银行"),
    ("证券|券商|期货|保险|金融|创投", "非银金融", "证券保险"),
    ("石油|油气|准油|油服|天然气|炼化", "石油石化", "油气开采"),
    ("药|医|生物|制药|医疗|健康|疫苗", "医药生物", "化学制药"),
    ("酒|食品|乳|饮料|糖|农牧|饲料", "食品饮料", "食品加工"),
    ("半导体|存储|芯|微|晶|电子|光电|电声|元器件|蓝天|共达", "电子", "半导体"),
    ("通信|光迅|烽火|通鼎|网络|光磁|CPO", "通信", "通信设备"),
    ("软件|信息|数据|云|智能|网达|南威|中国软件", "计算机", "软件开发"),
    ("机器人|机械|轴承|机床|工具|装备|巨轮|宝鼎|五洲新春|电机|传动", "机械设备", "通用设备"),
    ("航天|航空|航发|军工|北斗|卫星", "国防军工", "航天装备"),
    ("汽车|车|汽配|轮胎|飞龙|凌云", "汽车", "汽车零部件"),
    ("锂|铜|铝|金|矿|钴|镍|稀土|有色", "有色金属", "工业金属"),
    ("电缆|线缆|电气|电工|电网|变压|杭电|风电|光伏|储能|新能", "电力设备", "电网设备"),
    ("煤|能源|电力|发电|燃气|港电|水电|核电", "公用事业", "电力"),
    ("化工|材料|新材|合金|塑|玻璃|水泥|陶瓷", "基础化工", "化学制品"),
    ("环保|生态|水务|节能", "环保", "环境治理"),
    ("传媒|游戏|文化|影视|出版|完美世界", "传媒", "游戏"),
    ("港|物流|航运|运输|国泰", "交通运输", "物流"),
    ("建筑|建设|工程|装饰|建材", "建筑装饰", "基础建设"),
    ("纺织|服装|家居|家纺|梦洁", "纺织服饰", "服装家纺"),
    ("地产|物业|商业|百货", "房地产", "房地产开发"),
]


def calculate_market_sentiment(summary: dict[str, Any]) -> dict[str, Any]:
    limit_up_count = int(summary.get("limitUpCount") or summary.get("limit_up_count") or 0)
    limit_down_count = int(summary.get("limitDownCount") or summary.get("limit_down_count") or 0)
    broken_count = int(summary.get("brokenLimitCount") or summary.get("broken_board_count") or 0)
    max_height = int(summary.get("highestBoard") or summary.get("max_board_height") or 0)
    third_plus_count = int(summary.get("thirdPlusCount") or summary.get("three_board_plus_count") or 0)
    seal_rate = 1 - broken_count / max(1, limit_up_count + broken_count)
    limit_up_score = min(100, limit_up_count / 120 * 100)
    seal_score = max(0, min(100, seal_rate * 100))
    height_score = min(100, max_height / 7 * 100)
    third_plus_score = min(100, third_plus_count / 5 * 100)
    yesterday_premium_score = float(summary.get("yesterdayLimitUpPremiumScore") or 65)
    limit_down_penalty = min(12, limit_down_count / 80 * 12)
    score = (
        0.25 * limit_up_score
        + 0.20 * seal_score
        + 0.20 * height_score
        + 0.15 * third_plus_score
        + 0.20 * yesterday_premium_score
        - limit_down_penalty
    )
    score = round(max(0, min(100, score)), 2)
    if score >= 75:
        state = "强情绪"
    elif score >= 60:
        state = "可交易"
    elif score >= 45:
        state = "弱分歧"
    else:
        state = "退潮"
    return {
        "tradeDate": summary.get("tradeDate") or summary.get("trade_date"),
        "limitUpCount": limit_up_count,
        "limitDownCount": limit_down_count,
        "brokenBoardCount": broken_count,
        "sealRate": round(seal_rate, 4),
        "maxBoardHeight": max_height,
        "threeBoardPlusCount": third_plus_count,
        "yesterdayLimitUpPremium": float(summary.get("yesterdayLimitUpPremium") or 0),
        "indexTrendScore": float(summary.get("indexTrendScore") or 50),
        "marketSentimentScore": score,
        "marketState": state,
    }


def score_limit_up_signal(stock: dict[str, Any], sentiment: dict[str, Any], industry_heat: dict[str, Any]) -> dict[str, Any]:
    board_count = int(stock.get("boardHeight") or stock.get("board_count") or 1)
    market_score = min(20, float(sentiment.get("marketSentimentScore") or 0) * 0.20)
    industry_rank = int(industry_heat.get("industryHeatRank") or 999)
    industry_score = min(20, float(industry_heat.get("industryHeatScore") or 0) * 0.20)
    board_score = _board_height_score(board_count)
    seal_score = _seal_quality_score(stock, board_count)
    liquidity_score = _liquidity_score(stock)
    risk_penalty, risk_reasons = _risk_penalty(stock, sentiment, industry_heat, board_count)
    total = market_score + industry_score + board_score + seal_score + liquidity_score + risk_penalty
    if industry_rank > 8:
        total -= 6
        risk_reasons.append("所属行业未进入 Top 8 热点行业，主线确认度不足。")
    total = round(max(0, min(100, total)), 2)
    hard_risk = _has_hard_risk(stock, sentiment)
    if hard_risk:
        total = min(total, 49)
    action_level, action_label = _action_level(total, sentiment, industry_rank, hard_risk)
    trigger_condition = _trigger_condition(action_label, board_count)
    return {
        "marketSentimentScore": round(float(sentiment.get("marketSentimentScore") or 0), 2),
        "industryHeatScore": round(float(industry_heat.get("industryHeatScore") or 0), 2),
        "industryHeatRank": industry_rank,
        "industryLineType": industry_heat.get("industryLineType") or "非主线",
        "boardHeightScore": board_score,
        "sealQualityScore": seal_score,
        "liquidityScore": liquidity_score,
        "riskPenaltyScore": round(risk_penalty, 2),
        "totalScore": total,
        "actionLevel": action_level,
        "actionLabel": action_label,
        "triggerCondition": trigger_condition,
        "positionAdvice": _position_advice(action_label, sentiment, board_count, industry_rank),
        "stopLossRule": "单笔亏损达到 -5%；跌破前一日涨停价；断板后次日低开且无法收回；高位放量炸板；跌破分时均价线且无法回封。",
        "takeProfitRule": "连续加速后放量炸板分批止盈；收益达到 15%-25% 根据封板强度分批止盈；断板且行业热度下降退出；市场情绪由强转弱时降低仓位。",
        "riskReasons": risk_reasons or ["未触发硬风险，但仍需盘中确认封板质量和行业持续性。"],
    }


def get_market_sentiment(trade_date: str | None = None) -> dict[str, Any]:
    analysis = generate_limit_up_strategy_analysis(trade_date=trade_date)
    return analysis["marketSentiment"]


def get_industry_heat(trade_date: str | None = None) -> list[dict[str, Any]]:
    analysis = generate_limit_up_strategy_analysis(trade_date=trade_date)
    return analysis["industryHeat"]


def get_limit_up_strategy_signals(
    trade_date: str | None = None,
    action_label: str | None = None,
    min_score: float | None = None,
    industry: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    return generate_limit_up_strategy_analysis(
        trade_date=trade_date,
        action_label=action_label,
        min_score=min_score,
        industry=industry,
        search=keyword,
        persist=True,
    )


def generate_limit_up_strategy_analysis(
    trade_date: str | None = None,
    height_filter: str = "all",
    market_filter: str = "all",
    search: str | None = None,
    action_label: str | None = None,
    min_score: float | None = None,
    industry: str | None = None,
    exclude_st: bool = False,
    mainline_only: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    target = trade_date or target_trade_date()
    ensure_industry_mapping(target)
    base = get_limit_up_stats(trade_date=target, height_filter=height_filter, market_filter=market_filter, search=search)
    items = [dict(item) for item in base["items"]]
    sentiment = calculate_market_sentiment(base["summary"])
    industry_heat = _calculate_industry_heat(items)
    heat_by_name = {item["industryName"]: item for item in industry_heat}
    enriched: list[dict[str, Any]] = []
    for stock in items:
        sw_l1 = stock.get("swL1Name") or stock.get("industry") or "综合"
        stock["industry"] = sw_l1
        heat = heat_by_name.get(sw_l1) or _default_heat(sw_l1)
        signal = score_limit_up_signal(stock, sentiment, heat)
        merged = {**stock, **signal}
        if exclude_st and _is_st(stock):
            continue
        if action_label and action_label != "all" and merged["actionLabel"] != action_label:
            continue
        if min_score is not None and float(merged["totalScore"]) < min_score:
            continue
        if industry and industry != "all" and industry not in {merged.get("industry"), merged.get("swL1Name"), merged.get("swL2Name")}:
            continue
        if mainline_only and merged.get("industryLineType") not in {"主线板块", "次主线"}:
            continue
        enriched.append(merged)
    enriched.sort(key=lambda item: (_action_priority(item["actionLabel"]), -float(item["totalScore"]), -int(item["boardHeight"]), int(item.get("industryHeatRank") or 999), -float(item.get("amount") or 0)))
    groups = _regroup(enriched)
    result = {
        "strategyName": STRATEGY_NAME,
        "strategyNameEn": STRATEGY_NAME_EN,
        "strategyCode": STRATEGY_CODE,
        "summary": base["summary"],
        "marketSentiment": sentiment,
        "industryHeat": industry_heat,
        "groups": groups,
        "items": enriched,
        "filters": {
            **base.get("filters", {}),
            "actionLabel": action_label or "all",
            "minScore": min_score,
            "industry": industry or "all",
            "excludeST": exclude_st,
            "mainlineOnly": mainline_only,
        },
        "disclaimer": "本模块仅用于个人量化研究与策略复盘，不构成任何投资建议或交易指令。",
    }
    if persist:
        _persist_sentiment(target, sentiment)
        _persist_industry_heat(target, industry_heat)
        _persist_signals(target, enriched)
    return result


def run_flum_backtest(payload: dict[str, Any]) -> dict[str, Any]:
    start_date = payload.get("startDate") or payload.get("start_date") or _default_start_date()
    end_date = payload.get("endDate") or payload.get("end_date") or target_trade_date()
    initial_cash = float(payload.get("initialCapital") or payload.get("initial_cash") or 100000)
    fee_rate = float(payload.get("transactionCost") or payload.get("fee_rate") or 0.0003)
    slippage = float(payload.get("slippage") or 0.001)
    max_position = float(payload.get("maxPositionPerStock") or 0.05)
    max_holding_days = int(payload.get("maxHoldingDays") or 3)
    dates = _trading_dates(start_date, end_date)
    if len(dates) < 2:
        return _empty_flum_backtest(start_date, end_date, initial_cash, "数据不足")

    cash = initial_cash
    equity_curve: list[dict[str, Any]] = []
    drawdown_curve: list[dict[str, Any]] = []
    daily_returns: list[float] = []
    trades: list[dict[str, Any]] = []
    returns_by_height: dict[str, list[float]] = defaultdict(list)
    returns_by_industry: dict[str, list[float]] = defaultdict(list)
    returns_by_sentiment: dict[str, list[float]] = defaultdict(list)
    rolling_max = initial_cash
    for idx, trade_date in enumerate(dates[:-1]):
        next_date = dates[idx + 1]
        analysis = generate_limit_up_strategy_analysis(trade_date=trade_date, action_label="可参与", persist=False)
        candidates = [item for item in analysis["items"] if item["actionLabel"] == "可参与" and not item.get("isOneWordBoard")]
        picks = candidates[:3]
        portfolio_return = 0.0
        for pick in picks:
            entry = _snapshot_price(pick["code"], next_date)
            exit_index = min(idx + 1 + max_holding_days, len(dates) - 1)
            exit_date = dates[exit_index]
            exit_price = _snapshot_price(pick["code"], exit_date)
            if not entry or not exit_price:
                continue
            raw_return = exit_price / entry - 1
            net_return = raw_return - fee_rate * 2 - slippage * 2
            weight = min(max_position, 1 / max(1, len(picks)))
            portfolio_return += weight * net_return
            trade = {
                "entryDate": next_date,
                "exitDate": exit_date,
                "code": pick["code"],
                "name": pick["name"],
                "industry": pick.get("industry"),
                "boardHeight": pick.get("boardHeight"),
                "marketState": analysis["marketSentiment"]["marketState"],
                "returnRate": round(net_return, 5),
                "holdingDays": exit_index - idx,
                "exitReason": "达到最大持仓天数或回测期结束",
            }
            trades.append(trade)
            returns_by_height[str(pick.get("boardHeight"))].append(net_return)
            returns_by_industry[str(pick.get("industry") or "综合")].append(net_return)
            returns_by_sentiment[analysis["marketSentiment"]["marketState"]].append(net_return)
        cash *= 1 + portfolio_return
        daily_returns.append(portfolio_return)
        rolling_max = max(rolling_max, cash)
        equity_curve.append({"date": next_date, "value": round(cash, 2), "return": round(portfolio_return, 5)})
        drawdown_curve.append({"date": next_date, "value": round(cash / rolling_max - 1, 5)})

    total_return = cash / initial_cash - 1
    max_drawdown = abs(min([point["value"] for point in drawdown_curve], default=0))
    win_rate = len([trade for trade in trades if trade["returnRate"] > 0]) / len(trades) if trades else 0
    wins = [trade["returnRate"] for trade in trades if trade["returnRate"] > 0]
    losses = [abs(trade["returnRate"]) for trade in trades if trade["returnRate"] < 0]
    profit_loss_ratio = (np.mean(wins) / np.mean(losses)) if wins and losses else 0
    std = float(np.std(daily_returns)) if daily_returns else 0
    sharpe = float(np.mean(daily_returns) / std * math.sqrt(252)) if std else 0
    annual_return = (cash / initial_cash) ** (252 / max(1, len(daily_returns))) - 1 if cash > 0 else -1
    validity = "可信" if len(trades) >= 30 and len(dates) >= 120 else "样本不足"
    return {
        "strategyName": STRATEGY_NAME,
        "strategyCode": STRATEGY_CODE,
        "startDate": start_date,
        "endDate": end_date,
        "totalReturn": round(total_return, 6),
        "annualReturn": round(annual_return, 6),
        "maxDrawdown": round(max_drawdown, 6),
        "winRate": round(win_rate, 6),
        "profitLossRatio": round(float(profit_loss_ratio or 0), 4),
        "sharpe": round(sharpe, 4),
        "tradeCount": len(trades),
        "avgHoldingDays": round(float(np.mean([trade["holdingDays"] for trade in trades])) if trades else 0, 2),
        "maxSingleLoss": round(min([trade["returnRate"] for trade in trades], default=0), 5),
        "consecutiveLossCount": _max_consecutive_losses(trades),
        "heightPerformance": _summarize_group_returns(returns_by_height),
        "industryPerformance": _summarize_group_returns(returns_by_industry),
        "sentimentPerformance": _summarize_group_returns(returns_by_sentiment),
        "equityCurve": equity_curve,
        "drawdownCurve": drawdown_curve,
        "trades": trades,
        "validityLevel": validity,
        "warnings": ["一字板默认不可成交；回测使用本地日线和快照数据，封板时间/炸板次数缺失时按降级规则估算。"],
        "disclaimer": "FLUM 回测仅用于策略研究与复盘，不代表未来收益，不构成投资建议。",
    }


def ensure_industry_mapping(trade_date: str | None = None) -> None:
    target = trade_date or target_trade_date()
    timestamp = now_iso()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.code, s.name, s.industry, ms.industry AS snapshot_industry
            FROM stocks s
            LEFT JOIN market_snapshots_daily ms ON ms.stock_code = s.code AND ms.trade_date = ?
            LEFT JOIN stock_industry_map im ON im.stock_code = s.code AND im.effective_date = ?
            WHERE im.stock_code IS NULL
               OR im.sw_l1_name IN ('', '综合', '未分类', '行业待映射')
               OR s.industry IN ('', '综合', '未分类', '行业待映射')
               OR ms.industry IN ('', '综合', '未分类', '行业待映射')
            """,
            (target, target),
        ).fetchall()
        values = []
        for row in dicts_from_rows(rows):
            snapshot_industry = row.get("snapshot_industry")
            stock_industry = row.get("industry")
            source_industry = snapshot_industry if snapshot_industry not in {"未分类", "综合", "行业待映射", "", None} else stock_industry
            l1, l2 = _classify_industry(row["code"], row["name"], source_industry)
            values.append((row["code"], row["name"], "", l1, "", l2, "", "", "akshare_sw_or_keyword_fallback", target, timestamp))
        if values:
            conn.executemany(
                """
                INSERT INTO stock_industry_map (
                    stock_code, stock_name, sw_l1_code, sw_l1_name, sw_l2_code, sw_l2_name,
                    sw_l3_code, sw_l3_name, source, effective_date, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stock_code, effective_date) DO UPDATE SET
                    stock_name = excluded.stock_name,
                    sw_l1_name = excluded.sw_l1_name,
                    sw_l2_name = excluded.sw_l2_name,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            conn.executemany(
                "UPDATE stocks SET industry = ?, updated_at = ? WHERE code = ? AND (industry IN ('未分类', '综合', '行业待映射') OR industry = '' OR industry IS NULL)",
                [(value[3], timestamp, value[0]) for value in values],
            )
            conn.executemany(
                "UPDATE market_snapshots_daily SET industry = ?, updated_at = ? WHERE trade_date = ? AND stock_code = ? AND (industry IN ('未分类', '综合', '行业待映射') OR industry = '' OR industry IS NULL)",
                [(value[3], timestamp, target, value[0]) for value in values],
            )


def _calculate_industry_heat(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        industry = item.get("swL1Name") or item.get("industry") or "综合"
        buckets[industry].append(item)
    raw = []
    for industry, rows in buckets.items():
        raw.append(
            {
                "industryLevel": "申万一级",
                "industryCode": "",
                "industryName": industry,
                "limitUpCount": len(rows),
                "chainStockCount": len([row for row in rows if int(row.get("boardHeight") or 1) >= 2]),
                "maxBoardHeight": max([int(row.get("boardHeight") or 1) for row in rows], default=1),
                "avgChangePct": round(float(np.mean([float(row.get("pctChange") or 0) for row in rows])), 2),
                "totalAmount": round(sum(float(row.get("amount") or 0) for row in rows), 2),
                "amountRatio": 1.0,
                "sealRate": 1.0,
                "brokenBoardCount": 0,
            }
        )
    if not raw:
        return []
    ranked_limit = _rank_scores(raw, "limitUpCount")
    ranked_height = _rank_scores(raw, "maxBoardHeight")
    ranked_pct = _rank_scores(raw, "avgChangePct")
    ranked_amount = _rank_scores(raw, "totalAmount")
    for idx, item in enumerate(raw):
        score = 0.35 * ranked_limit[idx] + 0.25 * ranked_height[idx] + 0.20 * ranked_pct[idx] + 0.20 * ranked_amount[idx]
        if item["industryName"] in {"综合", "未分类", "行业待映射"}:
            score = min(score, 32)
        item["industryHeatScore"] = round(score, 2)
    raw.sort(key=lambda item: (-float(item["industryHeatScore"]), -int(item["limitUpCount"]), -int(item["maxBoardHeight"])))
    for rank, item in enumerate(raw, start=1):
        item["industryHeatRank"] = rank
        item["industryLineType"] = "主线板块" if rank <= 3 else "次主线" if rank <= 8 else "非主线"
    return raw


def _persist_sentiment(trade_date: str, sentiment: dict[str, Any]) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO market_sentiment_daily (
                trade_date, limit_up_count, limit_down_count, broken_board_count, seal_rate,
                max_board_height, three_board_plus_count, yesterday_limit_up_premium,
                index_trend_score, market_sentiment_score, market_state, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date) DO UPDATE SET
                limit_up_count = excluded.limit_up_count,
                limit_down_count = excluded.limit_down_count,
                broken_board_count = excluded.broken_board_count,
                seal_rate = excluded.seal_rate,
                max_board_height = excluded.max_board_height,
                three_board_plus_count = excluded.three_board_plus_count,
                market_sentiment_score = excluded.market_sentiment_score,
                market_state = excluded.market_state,
                updated_at = excluded.updated_at
            """,
            (
                trade_date,
                sentiment["limitUpCount"],
                sentiment["limitDownCount"],
                sentiment["brokenBoardCount"],
                sentiment["sealRate"],
                sentiment["maxBoardHeight"],
                sentiment["threeBoardPlusCount"],
                sentiment["yesterdayLimitUpPremium"],
                sentiment["indexTrendScore"],
                sentiment["marketSentimentScore"],
                sentiment["marketState"],
                timestamp,
                timestamp,
            ),
        )


def _persist_industry_heat(trade_date: str, rows: list[dict[str, Any]]) -> None:
    timestamp = now_iso()
    values = [
        (
            trade_date,
            item["industryLevel"],
            item.get("industryCode") or "",
            item["industryName"],
            item["limitUpCount"],
            item["chainStockCount"],
            item["maxBoardHeight"],
            item["avgChangePct"],
            item["totalAmount"],
            item["amountRatio"],
            item["sealRate"],
            item["brokenBoardCount"],
            item["industryHeatScore"],
            item["industryHeatRank"],
            timestamp,
            timestamp,
        )
        for item in rows
    ]
    if not values:
        return
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO industry_heat_daily (
                trade_date, industry_level, industry_code, industry_name, limit_up_count,
                chain_stock_count, max_board_height, avg_change_pct, total_amount, amount_ratio,
                seal_rate, broken_board_count, industry_heat_score, industry_heat_rank, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, industry_level, industry_name) DO UPDATE SET
                limit_up_count = excluded.limit_up_count,
                chain_stock_count = excluded.chain_stock_count,
                max_board_height = excluded.max_board_height,
                avg_change_pct = excluded.avg_change_pct,
                total_amount = excluded.total_amount,
                industry_heat_score = excluded.industry_heat_score,
                industry_heat_rank = excluded.industry_heat_rank,
                updated_at = excluded.updated_at
            """,
            values,
        )


def _persist_signals(trade_date: str, items: list[dict[str, Any]]) -> None:
    timestamp = now_iso()
    values = []
    for item in items:
        values.append(
            (
                trade_date,
                item["code"],
                item["name"],
                int(item.get("boardHeight") or 1),
                item.get("swL1Name") or item.get("industry") or "综合",
                item.get("swL2Name") or item.get("industry") or "综合",
                item["marketSentimentScore"],
                item["industryHeatScore"],
                item["boardHeightScore"],
                item["sealQualityScore"],
                item["liquidityScore"],
                item["riskPenaltyScore"],
                item["totalScore"],
                item["actionLevel"],
                item["actionLabel"],
                item["triggerCondition"],
                item["positionAdvice"],
                item["stopLossRule"],
                item["takeProfitRule"],
                json.dumps(item["riskReasons"], ensure_ascii=False),
                timestamp,
                timestamp,
            )
        )
    if not values:
        return
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO limit_up_strategy_signals (
                trade_date, stock_code, stock_name, board_count, sw_l1_name, sw_l2_name,
                market_sentiment_score, industry_heat_score, board_height_score, seal_quality_score,
                liquidity_score, risk_penalty_score, total_score, action_level, action_label,
                trigger_condition, position_advice, stop_loss_rule, take_profit_rule, risk_reasons,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, stock_code) DO UPDATE SET
                board_count = excluded.board_count,
                sw_l1_name = excluded.sw_l1_name,
                sw_l2_name = excluded.sw_l2_name,
                market_sentiment_score = excluded.market_sentiment_score,
                industry_heat_score = excluded.industry_heat_score,
                board_height_score = excluded.board_height_score,
                seal_quality_score = excluded.seal_quality_score,
                liquidity_score = excluded.liquidity_score,
                risk_penalty_score = excluded.risk_penalty_score,
                total_score = excluded.total_score,
                action_level = excluded.action_level,
                action_label = excluded.action_label,
                trigger_condition = excluded.trigger_condition,
                position_advice = excluded.position_advice,
                stop_loss_rule = excluded.stop_loss_rule,
                take_profit_rule = excluded.take_profit_rule,
                risk_reasons = excluded.risk_reasons,
                updated_at = excluded.updated_at
            """,
            values,
        )


def _classify_industry(code: str, name: str, source_industry: str | None) -> tuple[str, str]:
    if source_industry and source_industry not in {"未分类", "综合", "行业待映射", ""}:
        return source_industry, source_industry
    import re

    for pattern, l1, l2 in INDUSTRY_KEYWORDS:
        if re.search(pattern, name, re.IGNORECASE):
            return l1, l2
    if code.startswith(("300", "688")):
        return "电子", "科技成长"
    if code.startswith(("8", "4", "9")):
        return "北交所", "专精特新"
    return "行业待映射", "行业待映射"


def _rank_scores(items: list[dict[str, Any]], key: str) -> list[float]:
    values = [float(item.get(key) or 0) for item in items]
    high = max(values) if values else 0
    low = min(values) if values else 0
    if high == low:
        return [80.0 for _ in values]
    return [40 + (value - low) / (high - low) * 60 for value in values]


def _board_height_score(board_count: int) -> float:
    return {1: 5, 2: 12, 3: 15, 4: 14, 5: 10}.get(board_count, 8)


def _seal_quality_score(stock: dict[str, Any], board_count: int) -> float:
    score = 15.0
    if stock.get("isOneWordBoard"):
        score -= 5 if board_count >= 3 else 2
    if stock.get("isNewHigh"):
        score += 2
    turnover = float(stock.get("turnoverRate") or 0)
    if 5 <= turnover <= 20:
        score += 3
    elif turnover > 35:
        score -= 6
    if board_count >= 6:
        score -= 4
    return round(max(0, min(20, score)), 2)


def _liquidity_score(stock: dict[str, Any]) -> float:
    amount = float(stock.get("amount") or 0)
    turnover = float(stock.get("turnoverRate") or 0)
    amount_score = min(9, amount / 2_000_000_000 * 9)
    if 5 <= turnover <= 20:
        turnover_score = 6
    elif 2 <= turnover < 5 or 20 < turnover <= 35:
        turnover_score = 4
    elif turnover > 35:
        turnover_score = 1
    else:
        turnover_score = 2
    return round(max(0, min(15, amount_score + turnover_score)), 2)


def _risk_penalty(stock: dict[str, Any], sentiment: dict[str, Any], industry_heat: dict[str, Any], board_count: int) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons: list[str] = []
    if _is_st(stock):
        penalty -= 30
        reasons.append("ST / *ST 股票触发硬风险过滤。")
    if sentiment.get("marketState") == "退潮":
        penalty -= 30
        reasons.append("市场情绪处于退潮，连板接力风险显著升高。")
    if board_count >= 6:
        penalty -= 8
        reasons.append("6板及以上高位连板，继续加速风险较高。")
    if stock.get("isOneWordBoard") and board_count >= 3:
        penalty -= 8
        reasons.append("高位连续一字板，可成交性和流动性较弱。")
    amount = float(stock.get("amount") or 0)
    if amount < 100_000_000:
        penalty -= 8
        reasons.append("成交额低于 1 亿元，流动性不足。")
    turnover = float(stock.get("turnoverRate") or 0)
    if turnover > 35:
        penalty -= 8
        reasons.append("换手率超过 35%，高位分歧和筹码松动风险较高。")
    if int(industry_heat.get("industryHeatRank") or 999) > 8:
        penalty -= 6
    return max(-30, penalty), reasons


def _has_hard_risk(stock: dict[str, Any], sentiment: dict[str, Any]) -> bool:
    return _is_st(stock) or sentiment.get("marketState") == "退潮"


def _is_st(stock: dict[str, Any]) -> bool:
    return bool(stock.get("isST") or "ST" in str(stock.get("name") or "").upper())


def _action_level(total: float, sentiment: dict[str, Any], industry_rank: int, hard_risk: bool) -> tuple[str, str]:
    if hard_risk or total < 50:
        return "D", "禁止参与"
    if total >= 80 and float(sentiment.get("marketSentimentScore") or 0) >= 60 and industry_rank <= 3:
        return "A", "可参与"
    if total >= 65:
        return "B", "观察"
    return "C", "回避"


def _action_priority(label: str) -> int:
    return {"可参与": 0, "观察": 1, "回避": 2, "禁止参与": 3}.get(label, 4)


def _trigger_condition(action_label: str, board_count: int) -> str:
    if action_label == "可参与":
        return "次日开盘涨幅 0%-5%，且 10:30 前放量回封；所属行业热度保持 Top 3；盘中不跌破昨日涨停价；炸板次数不超过 2 次。"
    if action_label == "观察":
        return "等待换手放量、行业内更多涨停确认，或分歧后回封；次日不低开破位再复核。"
    return "不生成参与触发条件；仅用于风险跟踪和复盘。"


def _position_advice(action_label: str, sentiment: dict[str, Any], board_count: int, industry_rank: int) -> str:
    if action_label != "可参与":
        return f"0 仓位或仅观察；{DISCLAIMER}"
    if board_count >= 5:
        return f"单票不超过 3%，仅限盘中触发条件确认；{DISCLAIMER}"
    if sentiment.get("marketState") == "强情绪" and industry_rank <= 3:
        return f"单票 5%-8%，总短线仓位不超过 30%；{DISCLAIMER}"
    return f"单票 3%-5%，总短线仓位不超过 15%；{DISCLAIMER}"


def _regroup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[int(item.get("boardHeight") or 1)].append(item)
    highest = max(grouped.keys(), default=0)
    return [
        {
            "height": height,
            "label": "最高板" if height == highest and height > 1 else f"{height}连板" if height > 1 else "首板",
            "stocks": grouped[height],
        }
        for height in sorted(grouped.keys(), reverse=True)
    ]


def _default_heat(industry: str) -> dict[str, Any]:
    return {"industryName": industry or "综合", "industryHeatScore": 35, "industryHeatRank": 999, "industryLineType": "非主线"}


def _trading_dates(start_date: str, end_date: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date AS trade_date FROM daily_prices WHERE date BETWEEN ? AND ?
            UNION
            SELECT trade_date FROM market_snapshots_daily WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            (start_date, end_date, start_date, end_date),
        ).fetchall()
    return [row["trade_date"] for row in rows]


def _snapshot_price(code: str, trade_date: str) -> float | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(ms.close, dp.close) AS close
            FROM daily_prices dp
            LEFT JOIN market_snapshots_daily ms ON ms.stock_code = dp.stock_code AND ms.trade_date = dp.date
            WHERE dp.stock_code = ? AND dp.date = ?
            """,
            (code, trade_date),
        ).fetchone()
    return float(row["close"]) if row and row["close"] else None


def _default_start_date() -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT MIN(date) AS d FROM daily_prices").fetchone()
    return row["d"] if row and row["d"] else target_trade_date()


def _empty_flum_backtest(start_date: str, end_date: str, initial_cash: float, validity: str) -> dict[str, Any]:
    return {
        "strategyName": STRATEGY_NAME,
        "strategyCode": STRATEGY_CODE,
        "startDate": start_date,
        "endDate": end_date,
        "totalReturn": 0,
        "annualReturn": 0,
        "maxDrawdown": 0,
        "winRate": 0,
        "profitLossRatio": 0,
        "sharpe": 0,
        "tradeCount": 0,
        "avgHoldingDays": 0,
        "maxSingleLoss": 0,
        "consecutiveLossCount": 0,
        "heightPerformance": [],
        "industryPerformance": [],
        "sentimentPerformance": [],
        "equityCurve": [{"date": end_date, "value": initial_cash, "return": 0}],
        "drawdownCurve": [{"date": end_date, "value": 0}],
        "trades": [],
        "validityLevel": validity,
        "warnings": ["历史行情覆盖不足，无法形成有效 FLUM 回测。"],
        "disclaimer": "FLUM 回测仅用于策略研究与复盘，不代表未来收益，不构成投资建议。",
    }


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int:
    best = 0
    current = 0
    for trade in trades:
        if float(trade.get("returnRate") or 0) < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _summarize_group_returns(groups: dict[str, list[float]]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "count": len(values),
            "avgReturn": round(float(np.mean(values)), 5) if values else 0,
            "winRate": round(len([value for value in values if value > 0]) / len(values), 4) if values else 0,
        }
        for name, values in sorted(groups.items(), key=lambda item: item[0])
    ]
