from __future__ import annotations

from app.db.database import dict_from_row, dicts_from_rows, get_connection
from app.services.strategy_service import list_signals


def risk_overview() -> dict:
    signals = list_signals(only_today=True)
    high_risk = [signal for signal in signals if signal["risk_level"] == "high"]
    medium_risk = [signal for signal in signals if signal["risk_level"] == "medium"]
    industry_counts: dict[str, int] = {}
    for signal in signals:
        industry = signal.get("industry") or "未知"
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
    total = max(1, len(signals))
    concentration = [
        {"industry": industry, "count": count, "ratio": round(count / total, 4)}
        for industry, count in sorted(industry_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    warnings = []
    if high_risk:
        warnings.append(f"{len(high_risk)} 只股票触发高风险观察")
    if concentration and concentration[0]["ratio"] > 0.35:
        warnings.append(f"{concentration[0]['industry']} 行业集中度偏高")
    latest_backtest = _latest_backtest()
    if latest_backtest and latest_backtest["max_drawdown"] > 0.18:
        warnings.append("最近回测最大回撤超过阈值，策略需降权观察")
    if not warnings:
        warnings.append("当前候选池未触发主要组合级风控预警")
    return {
        "single_position_limit": _rule_threshold("单票最大仓位", 0.2),
        "total_position_suggestion": 0.65 if high_risk else 0.8,
        "industry_concentration": concentration,
        "high_risk_count": len(high_risk),
        "medium_risk_count": len(medium_risk),
        "blacklist": [],
        "high_risk_pool": high_risk,
        "warnings": warnings,
        "latest_backtest": latest_backtest,
    }


def list_risk_rules() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM risk_rules ORDER BY id").fetchall()
    rules = dicts_from_rows(rows)
    for rule in rules:
        rule["enabled"] = bool(rule["enabled"])
    return rules


def update_risk_rule(rule_id: int, payload: dict) -> dict | None:
    current = get_risk_rule(rule_id)
    if not current:
        return None
    threshold = payload.get("threshold", current["threshold"])
    enabled = payload.get("enabled", current["enabled"])
    description = payload.get("description", current["description"])
    with get_connection() as conn:
        conn.execute(
            "UPDATE risk_rules SET threshold = ?, enabled = ?, description = ? WHERE id = ?",
            (threshold, 1 if enabled else 0, description, rule_id),
        )
    return get_risk_rule(rule_id)


def get_risk_rule(rule_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM risk_rules WHERE id = ?", (rule_id,)).fetchone()
    rule = dict_from_row(row)
    if rule:
        rule["enabled"] = bool(rule["enabled"])
    return rule


def _rule_threshold(name: str, fallback: float) -> float:
    with get_connection() as conn:
        row = conn.execute("SELECT threshold FROM risk_rules WHERE name = ?", (name,)).fetchone()
    return float(row["threshold"]) if row else fallback


def _latest_backtest() -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                br.id,
                br.strategy_id,
                br.start_date,
                br.end_date,
                br.total_return,
                br.annual_return,
                br.max_drawdown,
                br.sharpe,
                br.win_rate,
                br.trade_count,
                br.created_at,
                st.name AS strategy_name
            FROM backtest_results br
            JOIN strategies st ON st.id = br.strategy_id
            ORDER BY br.created_at DESC
            LIMIT 1
            """
        ).fetchone()
    return dict_from_row(row)
