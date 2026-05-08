from __future__ import annotations

import json
from typing import Any

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services.backtest_service import check_backtest_validity

SOURCE_TYPES = {
    "academic_paper",
    "broker_research",
    "quant_firm_research",
    "public_blog",
    "book",
    "open_source",
    "self_developed",
    "inspired_by",
    "unknown",
}
CONFIDENCE_ORDER = {"低": 0, "中": 1, "高": 2}
VERSION = "v1"


DEFAULT_STRATEGY_SOURCES: dict[str, dict[str, Any]] = {
    "均线趋势策略": {
        "sourceType": "inspired_by",
        "sourceName": "经典趋势跟踪思想（公开研究启发）",
        "sourceTitle": "Time Series Momentum",
        "sourceAuthor": "Moskowitz, Ooi, Pedersen",
        "sourceUrl": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463",
        "publishDate": "2012",
        "sourceSummary": "参考时间序列动量和趋势跟踪思想，观察价格趋势延续与相对强度。",
        "originalIdea": "原始思想强调资产自身过去收益对未来一段时间收益有解释力，并通过趋势信号控制风险暴露。",
        "localAdaptation": "本系统使用 MA20/MA60、均线斜率、成交额、回撤、波动率和市场状态过滤做 A 股本地化改造。",
        "implementationNotes": "当前实现是本地化均线趋势观察版本，不等同于原论文或任何机构原始策略。",
        "limitations": ["未使用期货跨资产样本", "真实滑点、涨跌停约束和指数成分历史仍需继续完善"],
        "requiredData": ["日线行情", "成交额", "均线", "回撤", "波动率", "市场状态"],
        "missingData": ["完整指数成分历史", "真实滑点模型"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["趋势", "动量", "市场状态"],
    },
    "低回撤趋势策略": {
        "sourceType": "inspired_by",
        "sourceName": "低波动因子与趋势过滤公开思路改造",
        "sourceTitle": "Benchmarks as Limits to Arbitrage: Understanding the Low-Volatility Anomaly",
        "sourceAuthor": "Baker, Bradley, Wurgler",
        "sourceUrl": "https://www.hbs.edu/faculty/Pages/item.aspx?num=39353",
        "publishDate": "2011",
        "sourceSummary": "参考低波动异常和趋势过滤思想，优先观察回撤较小、波动可控且仍有趋势的股票。",
        "originalIdea": "低波动股票长期可能呈现较好的风险调整收益，趋势过滤用于避免弱势下跌资产。",
        "localAdaptation": "在 A 股环境中加入 60 日回撤、波动率、成交额和市场状态阈值。",
        "implementationNotes": "本系统为本地化改造版本，不等同于原论文策略。",
        "limitations": ["样本和交易成本会显著影响低波动因子表现", "行业暴露和拥挤度暂未完整建模"],
        "requiredData": ["日线行情", "成交额", "回撤", "波动率", "行业分类"],
        "missingData": ["完整行业中性约束", "交易成本实盘校准"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["低波", "趋势", "防御"],
    },
    "多因子评分策略": {
        "sourceType": "inspired_by",
        "sourceName": "公开多因子框架启发",
        "sourceTitle": "Common risk factors in the returns on stocks and bonds",
        "sourceAuthor": "Fama, French",
        "sourceUrl": "https://doi.org/10.1016/0304-405X(93)90023-5",
        "publishDate": "1993",
        "sourceSummary": "参考公开多因子研究框架，将动量、波动、成交量、回撤和趋势合成为观察评分。",
        "originalIdea": "通过多个风险因子或信号维度解释资产收益差异，避免单一指标判断。",
        "localAdaptation": "当前以本地日线和量价因子为主，先服务候选观察和复盘，不作为完整因子投资模型。",
        "implementationNotes": "本系统为简化评分版本，不等同于 Fama-French 原始因子模型。",
        "limitations": ["财务因子和行业中性处理不足", "缺少严格横截面回测和换手约束"],
        "requiredData": ["日线行情", "成交量", "回撤", "波动率", "趋势因子"],
        "missingData": ["完整财务公告日期", "行业中性回测"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["多因子", "动量", "风险控制"],
    },
    "短线龙头候选策略": {
        "sourceType": "self_developed",
        "sourceName": "自研 A 股短线情绪观察策略",
        "sourceTitle": None,
        "sourceAuthor": "Felix量化",
        "sourceUrl": None,
        "publishDate": None,
        "sourceSummary": "基于涨停、连板、板块联动、成交额和市场情绪识别短线强势候选。",
        "originalIdea": "A 股短线情绪常由涨停扩散、连板高度和板块跟随强度共同驱动。",
        "localAdaptation": "结合本地市场状态、成交额、回撤和风险池分层；关键数据缺失时只做降级观察。",
        "implementationNotes": "这是自研本地化观察策略，不声明来自任何量化机构或券商原版策略。",
        "limitations": ["高度依赖涨停、炸板、连板和题材数据", "缺少分时涨停时间会降低龙头辨识度"],
        "requiredData": ["日线行情", "涨停数据", "炸板数据", "连板数据", "题材数据", "板块资金"],
        "missingData": ["完整涨停池", "炸板数据", "连板高度", "概念题材数据"],
        "confidenceLevel": "低",
        "evidenceLevel": "仅假设",
        "tags": ["短线", "情绪", "龙头", "热点"],
    },
    "市场热点候选策略": {
        "sourceType": "self_developed",
        "sourceName": "自研 A 股热点跟踪策略",
        "sourceTitle": None,
        "sourceAuthor": "Felix量化",
        "sourceUrl": None,
        "publishDate": None,
        "sourceSummary": "基于涨幅、成交额、板块强度、题材热度和市场状态识别短期强势方向。",
        "originalIdea": "市场主线通常体现为板块涨幅、成交放大、强势股扩散和风险偏好恢复。",
        "localAdaptation": "缺少完整题材数据时使用行业涨幅、成交额放大和个股相对强度做降级估算。",
        "implementationNotes": "这是自研 A 股本地化热点观察策略，结果仅用于研究和人工确认。",
        "limitations": ["题材、涨停、炸板和连板数据缺失时可信度下降", "热点高波动阶段需要额外风控"],
        "requiredData": ["日线行情", "行业涨幅", "成交额", "题材数据", "涨停数据", "炸板数据"],
        "missingData": ["完整概念题材数据", "涨停/炸板/连板数据"],
        "confidenceLevel": "低",
        "evidenceLevel": "弱证据",
        "tags": ["热点", "短线", "情绪", "资金"],
    },
    "价值动量策略": {
        "sourceType": "quant_firm_research",
        "sourceName": "AQR 公开研究启发",
        "sourceTitle": "Value and Momentum Everywhere",
        "sourceAuthor": "Asness, Moskowitz, Pedersen",
        "sourceUrl": "https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere",
        "publishDate": "2013",
        "sourceSummary": "参考公开研究中价值因子与动量因子结合的思想，观察低估值与中期动量共振。",
        "originalIdea": "价值和动量是长期被研究的两类风险/行为因子，组合使用可能提升互补性。",
        "localAdaptation": "在 A 股中加入成交额、回撤、行业约束和市场状态过滤，避免直接照搬海外样本结论。",
        "implementationNotes": "本系统为公开研究启发的本地化改造版本，不等同于 AQR 原始策略。",
        "limitations": ["A 股财务字段和公告日期处理仍需完善", "估值因子当前含代理估算"],
        "requiredData": ["估值因子", "动量因子", "日线行情", "流动性", "行业分类"],
        "missingData": ["公告日期口径财务数据", "完整股息和自由现金流数据"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["价值", "动量", "多因子"],
    },
    "质量动量策略": {
        "sourceType": "quant_firm_research",
        "sourceName": "AQR 公开研究启发",
        "sourceTitle": "Quality Minus Junk",
        "sourceAuthor": "Asness, Frazzini, Pedersen",
        "sourceUrl": "https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk",
        "publishDate": "2019",
        "sourceSummary": "参考质量因子研究，将盈利质量、财务安全和中期动量结合为观察框架。",
        "originalIdea": "高质量公司通常在盈利能力、成长性、安全性和分红等维度表现较好。",
        "localAdaptation": "A 股第一版使用可得财务代理和趋势确认，并用数据可信度限制策略解释力度。",
        "implementationNotes": "本系统为公开研究启发的本地化改造版本，不等同于 AQR 原始策略。",
        "limitations": ["财务公告日期、生存者偏差和行业中性处理仍需完善", "现金流质量字段可能缺失"],
        "requiredData": ["ROE/ROA", "利润率", "现金流质量", "负债率", "成长性", "动量"],
        "missingData": ["公告日期口径财务数据", "完整现金流质量字段"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["质量", "动量", "多因子"],
    },
    "低波防御策略": {
        "sourceType": "academic_paper",
        "sourceName": "低波动因子公开论文启发",
        "sourceTitle": "Benchmarks as Limits to Arbitrage: Understanding the Low-Volatility Anomaly",
        "sourceAuthor": "Baker, Bradley, Wurgler",
        "sourceUrl": "https://www.hbs.edu/faculty/Pages/item.aspx?num=39353",
        "publishDate": "2011",
        "sourceSummary": "参考低波动因子思想，在弱市或震荡阶段观察低波、低回撤和流动性较好的股票。",
        "originalIdea": "低波动资产可能因为基准约束和杠杆限制等原因长期被低估。",
        "localAdaptation": "在 RiskOff/Choppy 状态下提高权重，并加入成交额、回撤和数据质量约束。",
        "implementationNotes": "本系统为本地化低波防御观察版本，不等同于原论文策略。",
        "limitations": ["行业暴露可能集中", "防御策略在 RiskOn 行情中可能跑输主线"],
        "requiredData": ["日线行情", "波动率", "回撤", "成交额", "行业分类"],
        "missingData": ["完整行业中性约束", "真实交易成本校准"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["低波", "防御", "风险控制"],
    },
    "趋势跟踪策略": {
        "sourceType": "academic_paper",
        "sourceName": "时间序列动量公开论文启发",
        "sourceTitle": "Time Series Momentum",
        "sourceAuthor": "Moskowitz, Ooi, Pedersen",
        "sourceUrl": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463",
        "publishDate": "2012",
        "sourceSummary": "参考趋势跟踪和时间序列动量思想，观察价格趋势延续、突破和回撤约束。",
        "originalIdea": "资产自身过去趋势可能在中短期延续，趋势反转或风险状态恶化时应降权。",
        "localAdaptation": "A 股版本加入 MA20/MA60、60/120 日收益、成交额、最大回撤和市场状态切换。",
        "implementationNotes": "本系统为本地化趋势观察模型，不等同于原论文跨资产策略。",
        "limitations": ["单市场股票样本与跨资产期货样本不同", "交易成本和滑点会影响趋势策略表现"],
        "requiredData": ["日线行情", "均线", "收益率", "成交额", "回撤", "市场状态"],
        "missingData": ["真实滑点模型", "完整指数成分历史"],
        "confidenceLevel": "中",
        "evidenceLevel": "中等证据",
        "tags": ["趋势", "动量", "突破"],
    },
}


def ensure_strategy_sources() -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        strategies = dicts_from_rows(conn.execute("SELECT name FROM strategies ORDER BY id").fetchall())
        rows = []
        for strategy in strategies:
            source = _source_for_strategy(strategy["name"])
            rows.append(_source_insert_tuple(source, timestamp))
        conn.executemany(
            """
            INSERT INTO strategy_sources (
                strategy_name, source_type, source_name, source_title, source_author, source_url,
                publish_date, source_summary, original_idea, local_adaptation, implementation_notes,
                limitations_json, required_data_json, missing_data_json, confidence_level,
                evidence_level, is_verified_by_backtest, backtest_validity, tags_json, version,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy_name, version) DO UPDATE SET
                source_type = excluded.source_type,
                source_name = excluded.source_name,
                source_title = excluded.source_title,
                source_author = excluded.source_author,
                source_url = excluded.source_url,
                publish_date = excluded.publish_date,
                source_summary = excluded.source_summary,
                original_idea = excluded.original_idea,
                local_adaptation = excluded.local_adaptation,
                implementation_notes = excluded.implementation_notes,
                limitations_json = excluded.limitations_json,
                required_data_json = excluded.required_data_json,
                missing_data_json = excluded.missing_data_json,
                confidence_level = excluded.confidence_level,
                evidence_level = excluded.evidence_level,
                tags_json = excluded.tags_json,
                updated_at = excluded.updated_at
            """,
            rows,
        )
    refresh_strategy_source_credibility()


def list_strategy_sources() -> list[dict[str, Any]]:
    ensure_strategy_sources()
    with get_connection() as conn:
        rows = dicts_from_rows(conn.execute("SELECT * FROM strategy_sources ORDER BY strategy_name").fetchall())
    return [_row_to_source(row) for row in rows]


def get_strategy_source(strategy_name: str) -> dict[str, Any]:
    ensure_strategy_sources()
    with get_connection() as conn:
        row = dict_from_row(
            conn.execute(
                """
                SELECT *
                FROM strategy_sources
                WHERE strategy_name = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (strategy_name,),
            ).fetchone()
        )
    if row:
        return _row_to_source(row)
    return _row_to_source(_source_for_strategy(strategy_name))


def summarize_strategy_sources() -> dict[str, Any]:
    sources = list_strategy_sources()
    return {
        "totalCount": len(sources),
        "selfDevelopedCount": len([item for item in sources if item["sourceType"] == "self_developed"]),
        "publicResearchCount": len(
            [
                item
                for item in sources
                if item["sourceType"] in {"academic_paper", "quant_firm_research", "book", "open_source", "public_blog"}
            ]
        ),
        "brokerResearchCount": len([item for item in sources if item["sourceType"] == "broker_research"]),
        "insufficientBacktestCount": len([item for item in sources if item["backtestValidity"] in {"样本不足", "未验证", "数据不足"}]),
        "lowConfidenceCount": len([item for item in sources if item["confidenceLevel"] == "低"]),
        "unverifiedCount": len([item for item in sources if not item["isVerifiedByBacktest"]]),
    }


def refresh_strategy_source_credibility() -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        rows = dicts_from_rows(conn.execute("SELECT * FROM strategy_sources").fetchall())
        for row in rows:
            adjusted = _apply_credibility_rules(_row_to_source(row))
            conn.execute(
                """
                UPDATE strategy_sources
                SET confidence_level = ?,
                    evidence_level = ?,
                    is_verified_by_backtest = ?,
                    backtest_validity = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    adjusted["confidenceLevel"],
                    adjusted["evidenceLevel"],
                    1 if adjusted["isVerifiedByBacktest"] else 0,
                    adjusted["backtestValidity"],
                    timestamp,
                    row["id"],
                ),
            )


def _source_for_strategy(strategy_name: str) -> dict[str, Any]:
    base = DEFAULT_STRATEGY_SOURCES.get(strategy_name)
    if not base:
        base = {
            "sourceType": "self_developed",
            "sourceName": "自研策略",
            "sourceTitle": None,
            "sourceAuthor": "Felix量化",
            "sourceUrl": None,
            "publishDate": None,
            "sourceSummary": "当前策略为 Felix量化本地研究策略，尚未绑定明确公开论文或机构出处。",
            "originalIdea": "基于本地策略参数和量化研究流程生成观察信号。",
            "localAdaptation": "用于 A 股个人量化研究、观察清单生成和复盘，不构成投资建议。",
            "implementationNotes": "来源未绑定公开出处时不展示任何机构背书。",
            "limitations": ["缺少公开来源验证", "需要通过回测和实盘复盘继续检验"],
            "requiredData": ["日线行情", "策略参数", "回测结果"],
            "missingData": ["明确公开来源", "长期可信回测"],
            "confidenceLevel": "低",
            "evidenceLevel": "仅假设",
            "tags": ["自研", "待验证"],
        }
    source = {
        "strategyName": strategy_name,
        "version": VERSION,
        "updatedAt": now_iso(),
        **base,
    }
    source["sourceType"] = source["sourceType"] if source["sourceType"] in SOURCE_TYPES else "unknown"
    source.setdefault("limitations", [])
    source.setdefault("requiredData", [])
    source.setdefault("missingData", [])
    source.setdefault("tags", [])
    source.setdefault("backtestValidity", "未验证")
    source.setdefault("isVerifiedByBacktest", False)
    return _apply_credibility_rules(source)


def _source_insert_tuple(source: dict[str, Any], timestamp: str) -> tuple[Any, ...]:
    return (
        source["strategyName"],
        source["sourceType"],
        source["sourceName"],
        source.get("sourceTitle"),
        source.get("sourceAuthor"),
        source.get("sourceUrl"),
        source.get("publishDate"),
        source["sourceSummary"],
        source["originalIdea"],
        source["localAdaptation"],
        source["implementationNotes"],
        json.dumps(source.get("limitations", []), ensure_ascii=False),
        json.dumps(source.get("requiredData", []), ensure_ascii=False),
        json.dumps(source.get("missingData", []), ensure_ascii=False),
        source["confidenceLevel"],
        source["evidenceLevel"],
        1 if source.get("isVerifiedByBacktest") else 0,
        source.get("backtestValidity", "未验证"),
        json.dumps(source.get("tags", []), ensure_ascii=False),
        source.get("version", VERSION),
        timestamp,
        timestamp,
    )


def _row_to_source(row: dict[str, Any]) -> dict[str, Any]:
    source = {
        "strategyName": row.get("strategy_name") or row.get("strategyName"),
        "sourceType": row.get("source_type") or row.get("sourceType") or "unknown",
        "sourceName": row.get("source_name") or row.get("sourceName") or "",
        "sourceTitle": row.get("source_title") if "source_title" in row else row.get("sourceTitle"),
        "sourceAuthor": row.get("source_author") if "source_author" in row else row.get("sourceAuthor"),
        "sourceUrl": row.get("source_url") if "source_url" in row else row.get("sourceUrl"),
        "publishDate": row.get("publish_date") if "publish_date" in row else row.get("publishDate"),
        "sourceSummary": row.get("source_summary") or row.get("sourceSummary") or "",
        "originalIdea": row.get("original_idea") or row.get("originalIdea") or "",
        "localAdaptation": row.get("local_adaptation") or row.get("localAdaptation") or "",
        "implementationNotes": row.get("implementation_notes") or row.get("implementationNotes") or "",
        "limitations": _parse_json_list(row.get("limitations_json") or row.get("limitations")),
        "requiredData": _parse_json_list(row.get("required_data_json") or row.get("requiredData")),
        "missingData": _parse_json_list(row.get("missing_data_json") or row.get("missingData")),
        "confidenceLevel": row.get("confidence_level") or row.get("confidenceLevel") or "低",
        "evidenceLevel": row.get("evidence_level") or row.get("evidenceLevel") or "仅假设",
        "isVerifiedByBacktest": bool(row.get("is_verified_by_backtest") or row.get("isVerifiedByBacktest")),
        "backtestValidity": row.get("backtest_validity") or row.get("backtestValidity") or "未验证",
        "tags": _parse_json_list(row.get("tags_json") or row.get("tags")),
        "version": row.get("version") or VERSION,
        "updatedAt": row.get("updated_at") or row.get("updatedAt") or now_iso(),
    }
    return _apply_credibility_rules(source)


def _apply_credibility_rules(source: dict[str, Any]) -> dict[str, Any]:
    source = dict(source)
    evidence = source.get("evidenceLevel") or "仅假设"
    if source.get("sourceType") == "academic_paper" and source.get("sourceTitle") and source.get("sourceAuthor") and source.get("sourceUrl"):
        evidence = _max_evidence(evidence, "中等证据")
    elif source.get("sourceType") == "broker_research" and source.get("sourceTitle") and source.get("sourceName") and source.get("publishDate"):
        evidence = _max_evidence(evidence, "中等证据")
    elif source.get("sourceType") == "quant_firm_research" and source.get("sourceUrl"):
        evidence = _max_evidence(evidence, "中等证据")
    elif source.get("sourceType") in {"self_developed", "unknown"}:
        evidence = "仅假设" if source.get("sourceType") == "unknown" else evidence

    backtest_validity = _backtest_validity_for_strategy(str(source.get("strategyName") or ""))
    confidence = source.get("confidenceLevel") or "低"
    if backtest_validity != "可信":
        confidence = _cap_confidence(confidence, "中")
    if source.get("missingData"):
        confidence = _cap_confidence(confidence, "中")
    if source.get("sourceType") in {"self_developed", "unknown"} and backtest_validity != "可信":
        confidence = _cap_confidence(confidence, "低")
    source["confidenceLevel"] = confidence
    source["evidenceLevel"] = evidence
    source["backtestValidity"] = backtest_validity
    source["isVerifiedByBacktest"] = backtest_validity == "可信"
    return source


def _backtest_validity_for_strategy(strategy_name: str) -> str:
    if not strategy_name:
        return "未验证"
    with get_connection() as conn:
        row = dict_from_row(
            conn.execute(
                """
                SELECT br.*
                FROM backtest_results br
                JOIN strategies st ON st.id = br.strategy_id
                WHERE st.name = ?
                ORDER BY br.created_at DESC, br.id DESC
                LIMIT 1
                """,
                (strategy_name,),
            ).fetchone()
        )
    if not row:
        return "未验证"
    row["result_json"] = _parse_json(row.get("result_json"), {})
    validity = check_backtest_validity(row).get("validityLevel")
    if validity == "可信":
        return "可信"
    if validity in {"样本不足", "区间不足"}:
        return "样本不足"
    return "数据不足"


def _cap_confidence(confidence: str, max_level: str) -> str:
    if CONFIDENCE_ORDER.get(confidence, 0) > CONFIDENCE_ORDER[max_level]:
        return max_level
    return confidence


def _max_evidence(current: str, minimum: str) -> str:
    order = {"仅假设": 0, "弱证据": 1, "中等证据": 2, "强证据": 3}
    return current if order.get(current, 0) >= order[minimum] else minimum


def _parse_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value)]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default
