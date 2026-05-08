from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.core.config import MARKET_DATA_SOURCE
from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso
from app.services.akshare_provider import AkshareDataProvider, AkshareUnavailableError, infer_market
from app.services import task_service

ProgressCallback = Callable[[int, str], None]


def target_trade_date(day: date | None = None) -> str:
    cursor = day or date.today()
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor.isoformat()


def get_market_data_sync_status(trade_date: str | None = None) -> dict[str, Any]:
    target = trade_date or target_trade_date()
    running = task_service.find_running_task("sync_market_snapshot", target)
    with get_connection() as conn:
        status = conn.execute("SELECT * FROM market_data_sync_status WHERE trade_date = ?", (target,)).fetchone()
        latest = conn.execute("SELECT MAX(trade_date) AS trade_date FROM market_snapshots_daily").fetchone()
        latest_row = None
        if latest and latest["trade_date"]:
            latest_row = conn.execute(
                """
                SELECT trade_date, MAX(updated_at) AS updated_at, COUNT(*) AS total_count
                FROM market_snapshots_daily
                WHERE trade_date = ?
                GROUP BY trade_date
                """,
                (latest["trade_date"],),
            ).fetchone()
    row = dict_from_row(status) or {}
    if not running and row.get("status") in {"pending", "running"}:
        task_id = row.get("task_id")
        stale_task = task_service.get_task_run(int(task_id)) if task_id else None
        if not stale_task or stale_task.get("status") not in task_service.RUNNING_STATUSES:
            next_status = "success" if stale_task and stale_task.get("status") == "success" else "failed"
            stale_error = (
                (stale_task or {}).get("error_message")
                or row.get("error_message")
                or "行情同步任务已结束，但同步状态未正确收尾。请重新同步。"
            )
            _write_status(
                target,
                next_status,
                progress=100 if next_status == "success" else float((stale_task or {}).get("progress_percent") or row.get("progress") or 0),
                total_count=int((stale_task or {}).get("total_count") or row.get("total_count") or 0),
                success_count=int((stale_task or {}).get("success_count") or row.get("success_count") or 0),
                failed_count=int((stale_task or {}).get("failed_count") or row.get("failed_count") or 0),
                error_message=None if next_status == "success" else stale_error,
                task_id=int(task_id) if task_id else None,
                finished=True,
            )
            row.update(
                {
                    "status": next_status,
                    "progress": 100 if next_status == "success" else float((stale_task or {}).get("progress_percent") or row.get("progress") or 0),
                    "total_count": int((stale_task or {}).get("total_count") or row.get("total_count") or 0),
                    "success_count": int((stale_task or {}).get("success_count") or row.get("success_count") or 0),
                    "failed_count": int((stale_task or {}).get("failed_count") or row.get("failed_count") or 0),
                    "error_message": None if next_status == "success" else stale_error,
                    "task_id": int(task_id) if task_id else None,
                    "finished_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
    if running:
        row.update(
            {
                "status": running["status"],
                "progress": running["progress_percent"],
                "total_count": running["total_count"],
                "success_count": running["success_count"],
                "failed_count": running["failed_count"],
                "error_message": running["error_message"],
                "task_id": running["id"],
                "started_at": running["started_at"],
                "finished_at": running["finished_at"],
                "updated_at": running["updated_at"],
            }
        )
    latest_snapshot = dict_from_row(latest_row) or {}
    status_value = row.get("status") or "idle"
    target_ready = status_value == "success" and bool(row)
    return {
        "tradeDate": target,
        "latestTradeDate": latest_snapshot.get("trade_date"),
        "latestUpdatedAt": latest_snapshot.get("updated_at") or row.get("updated_at"),
        "status": status_value,
        "progress": float(row.get("progress") or 0),
        "totalCount": int(row.get("total_count") or latest_snapshot.get("total_count") or 0),
        "successCount": int(row.get("success_count") or 0),
        "failedCount": int(row.get("failed_count") or 0),
        "errorMessage": row.get("error_message"),
        "taskId": row.get("task_id"),
        "needsSync": not target_ready and not running,
        "isRunning": bool(running),
        "usingCacheDate": target if target_ready else latest_snapshot.get("trade_date"),
    }


def is_market_snapshot_synced(trade_date: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT status, success_count
            FROM market_data_sync_status
            WHERE trade_date = ?
            """,
            (trade_date,),
        ).fetchone()
    return bool(row and row["status"] == "success" and int(row["success_count"] or 0) > 0)


def sync_market_snapshot(
    trade_date: str | None = None,
    source: str | None = None,
    limit: int | None = None,
    force: bool = False,
    task_id: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    target = trade_date or target_trade_date()
    if not force and is_market_snapshot_synced(target):
        return {"tradeDate": target, "status": "success", "skipped": True, "reason": "今日行情已同步"}
    _write_status(target, "running", progress=0, total_count=0, success_count=0, failed_count=0, task_id=task_id)
    _notify(progress_callback, 0, "任务创建")
    try:
        _write_status(target, "running", progress=10, total_count=limit or 5000, task_id=task_id)
        _notify(progress_callback, 10, "开始同步数据")
        rows = _fetch_snapshot_rows(source=source, limit=limit)
        _notify(progress_callback, 30, f"市场数据获取完成，共 {len(rows)} 只股票")
        _write_status(target, "running", progress=30, total_count=len(rows), task_id=task_id)
        if not rows:
            raise AkshareUnavailableError("行情源未返回可入库股票。")
        success_count = _upsert_snapshot_rows(target, rows)
        _notify(progress_callback, 90, "正在刷新本地行情缓存")
        _write_status(target, "running", progress=90, total_count=len(rows), success_count=success_count, failed_count=max(0, len(rows) - success_count), task_id=task_id)
        _write_status(target, "success", progress=100, total_count=len(rows), success_count=success_count, failed_count=max(0, len(rows) - success_count), task_id=task_id, finished=True)
        return {
            "tradeDate": target,
            "status": "success",
            "totalCount": len(rows),
            "successCount": success_count,
            "failedCount": max(0, len(rows) - success_count),
            "updatedAt": now_iso(),
        }
    except Exception as exc:
        _write_status(target, "failed", error_message=str(exc), task_id=task_id, finished=True)
        raise


def get_limit_up_summary(trade_date: str | None = None) -> dict[str, Any]:
    target = _resolve_stats_date(trade_date)
    rows = _limit_up_rows(target)
    limit_rows = [row for row in rows if row["isLimitUp"]]
    grouped = _group_limit_rows(target, limit_rows)
    return _build_limit_up_summary(target, rows, grouped)


def get_limit_up_stats(
    trade_date: str | None = None,
    height_filter: str = "all",
    market_filter: str = "all",
    search: str | None = None,
) -> dict[str, Any]:
    target = _resolve_stats_date(trade_date)
    rows = _limit_up_rows(target)
    limit_rows = [row for row in rows if row["isLimitUp"]]
    grouped = _group_limit_rows(target, limit_rows)
    highest = max(grouped.keys(), default=0)
    items: list[dict[str, Any]] = []
    keyword = (search or "").strip().lower()
    new_high_map = _new_high_map(limit_rows, target)
    for height, group_rows in grouped.items():
        for row in group_rows:
            if not _match_height_filter(height, height_filter, highest):
                continue
            if not _match_market_filter(row["code"], market_filter):
                continue
            if keyword and keyword not in row["code"].lower() and keyword not in row["name"].lower():
                continue
            item = dict(row)
            item["boardHeight"] = height
            item["boardLabel"] = _height_label(height)
            item["sealTime"] = row.get("firstLimitTime") or row.get("lastLimitTime")
            item["sealAmount"] = row.get("sealAmount")
            item["isOneWordBoard"] = bool(row["open"] and row["open"] == row["high"] == row["low"] == row["close"])
            item["isNewHigh"] = bool(row.get("snapshotIsNewHigh") or new_high_map.get(row["code"]))
            items.append(item)
    items.sort(key=lambda item: (-int(item["boardHeight"]), -(float(item.get("amount") or 0))))
    groups: list[dict[str, Any]] = []
    for height in sorted({int(item["boardHeight"]) for item in items}, reverse=True):
        group_items = [item for item in items if int(item["boardHeight"]) == height]
        groups.append(
            {
                "height": height,
                "label": "最高板" if height == highest and height > 1 else _height_label(height),
                "stocks": group_items,
            }
        )
    return {
        "summary": _build_limit_up_summary(target, rows, grouped),
        "groups": groups,
        "items": items,
        "filters": {"height": height_filter, "market": market_filter, "search": search or ""},
    }


def _fetch_snapshot_rows(source: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    data_source = (source or MARKET_DATA_SOURCE or "akshare").lower()
    if data_source == "sample":
        return _sample_snapshot_rows(limit=limit)
    provider = AkshareDataProvider(include_industry=False)
    return provider.fetch_market_snapshot(limit=limit)


def _upsert_snapshot_rows(trade_date: str, rows: list[dict[str, Any]]) -> int:
    timestamp = now_iso()
    snapshot_values: list[tuple[Any, ...]] = []
    stock_values: list[tuple[Any, ...]] = []
    price_values: list[tuple[Any, ...]] = []
    for row in rows:
        code = row["stock_code"]
        name = row["stock_name"]
        if not code or not name or bool(row.get("is_suspended")):
            continue
        close = float(row.get("close") or 0)
        if close <= 0:
            continue
        market = row.get("market") or infer_market(code)
        industry = row.get("industry") or "未分类"
        stock_values.append((code, name, industry, market, int(bool(row.get("is_st"))), int(bool(row.get("is_suspended"))), float(row.get("float_market_value") or row.get("market_value") or 8000000000), timestamp, timestamp))
        snapshot_values.append(
            (
                trade_date,
                code,
                name,
                market,
                industry,
                _num(row.get("open")),
                _num(row.get("high")),
                _num(row.get("low")),
                close,
                _num(row.get("pre_close")),
                _num(row.get("change_pct")),
                _num(row.get("volume")),
                _num(row.get("amount")),
                _num(row.get("turnover_rate")),
                _num(row.get("market_value")),
                _num(row.get("float_market_value")),
                _num(row.get("limit_up_price")),
                _num(row.get("limit_down_price")),
                int(bool(row.get("is_limit_up"))),
                int(bool(row.get("is_limit_down"))),
                int(bool(row.get("is_suspended"))),
                int(bool(row.get("is_st"))),
                row.get("raw_json") or "{}",
                timestamp,
                timestamp,
            )
        )
        price_values.append((code, trade_date, _num(row.get("open")), _num(row.get("high")), _num(row.get("low")), close, _num(row.get("volume")), _num(row.get("amount")), _num(row.get("change_pct"))))
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO stocks (code, name, industry, market, is_st, is_suspended, float_market_cap, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                industry = CASE WHEN excluded.industry != '未分类' THEN excluded.industry ELSE stocks.industry END,
                market = excluded.market,
                is_st = excluded.is_st,
                is_suspended = excluded.is_suspended,
                float_market_cap = CASE WHEN excluded.float_market_cap > 0 THEN excluded.float_market_cap ELSE stocks.float_market_cap END,
                updated_at = excluded.updated_at
            """,
            stock_values,
        )
        conn.executemany(
            """
            INSERT INTO market_snapshots_daily (
                trade_date, stock_code, stock_name, market, industry, open, high, low, close, pre_close,
                change_pct, volume, amount, turnover_rate, market_value, float_market_value,
                limit_up_price, limit_down_price, is_limit_up, is_limit_down, is_suspended, is_st,
                raw_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, stock_code) DO UPDATE SET
                stock_name = excluded.stock_name,
                market = excluded.market,
                industry = excluded.industry,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                pre_close = excluded.pre_close,
                change_pct = excluded.change_pct,
                volume = excluded.volume,
                amount = excluded.amount,
                turnover_rate = excluded.turnover_rate,
                market_value = excluded.market_value,
                float_market_value = excluded.float_market_value,
                limit_up_price = excluded.limit_up_price,
                limit_down_price = excluded.limit_down_price,
                is_limit_up = excluded.is_limit_up,
                is_limit_down = excluded.is_limit_down,
                is_suspended = excluded.is_suspended,
                is_st = excluded.is_st,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            """,
            snapshot_values,
        )
        conn.executemany(
            """
            INSERT INTO daily_prices (stock_code, date, open, high, low, close, volume, amount, pct_change)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_code, date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                pct_change = excluded.pct_change
            """,
            price_values,
        )
    return len(snapshot_values)


def _write_status(
    trade_date: str,
    status: str,
    progress: float | None = None,
    total_count: int | None = None,
    success_count: int | None = None,
    failed_count: int | None = None,
    error_message: str | None = None,
    task_id: int | None = None,
    finished: bool = False,
) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        existing = conn.execute("SELECT * FROM market_data_sync_status WHERE trade_date = ?", (trade_date,)).fetchone()
        existing_row = dict_from_row(existing) or {}
        progress_value = progress if progress is not None else float(existing_row.get("progress") or 0)
        total_value = total_count if total_count is not None else int(existing_row.get("total_count") or 0)
        success_value = success_count if success_count is not None else int(existing_row.get("success_count") or 0)
        failed_value = failed_count if failed_count is not None else int(existing_row.get("failed_count") or 0)
        conn.execute(
            """
            INSERT INTO market_data_sync_status (
                trade_date, status, progress, total_count, success_count, failed_count,
                error_message, task_id, started_at, finished_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date) DO UPDATE SET
                status = excluded.status,
                progress = COALESCE(excluded.progress, market_data_sync_status.progress),
                total_count = COALESCE(excluded.total_count, market_data_sync_status.total_count),
                success_count = COALESCE(excluded.success_count, market_data_sync_status.success_count),
                failed_count = COALESCE(excluded.failed_count, market_data_sync_status.failed_count),
                error_message = excluded.error_message,
                task_id = COALESCE(excluded.task_id, market_data_sync_status.task_id),
                finished_at = COALESCE(excluded.finished_at, market_data_sync_status.finished_at),
                updated_at = excluded.updated_at
            """,
            (
                trade_date,
                status,
                progress_value,
                total_value,
                success_value,
                failed_value,
                error_message,
                task_id,
                timestamp,
                timestamp if finished else None,
                timestamp,
                timestamp,
            ),
        )


def _limit_up_rows(trade_date: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.code,
                s.name,
                s.industry AS stockIndustry,
                s.market,
                COALESCE(s.is_st, 0) AS isST,
                COALESCE(NULLIF(im.sw_l1_name, ''), NULLIF(ms.industry, '未分类'), NULLIF(s.industry, '未分类'), '综合') AS swL1Name,
                COALESCE(NULLIF(im.sw_l2_name, ''), NULLIF(im.sw_l1_name, ''), NULLIF(ms.industry, '未分类'), NULLIF(s.industry, '未分类'), '综合') AS swL2Name,
                COALESCE(im.sw_l3_name, '') AS swL3Name,
                COALESCE(ms.open, dp.open) AS open,
                COALESCE(ms.high, dp.high) AS high,
                COALESCE(ms.low, dp.low) AS low,
                COALESCE(ms.close, dp.close) AS close,
                COALESCE(ms.change_pct, dp.pct_change) AS pctChange,
                COALESCE(ms.amount, dp.amount) AS amount,
                ms.turnover_rate AS turnoverRate,
                COALESCE(ms.float_market_value, s.float_market_cap, 0) AS floatMarketCap,
                COALESCE(ms.limit_up_price, 0) AS limitUpPrice,
                COALESCE(ms.limit_down_price, 0) AS limitDownPrice,
                COALESCE(ms.is_limit_up, 0) AS snapshotLimitUp,
                COALESCE(ms.is_limit_down, 0) AS snapshotLimitDown,
                COALESCE(ms.is_broken_board, 0) AS isBrokenBoard,
                ms.first_limit_time AS firstLimitTime,
                ms.last_limit_time AS lastLimitTime,
                COALESCE(ms.open_board_count, 0) AS openBoardCount,
                COALESCE(ms.seal_amount, 0) AS sealAmount,
                COALESCE(ms.seal_amount_ratio, 0) AS sealAmountRatio,
                COALESCE(ms.limit_up_type, '未知') AS limitUpType,
                COALESCE(ms.is_new_high, 0) AS snapshotIsNewHigh,
                COALESCE(ms.updated_at, '') AS updatedAt
            FROM stocks s
            JOIN daily_prices dp ON dp.stock_code = s.code AND dp.date = ?
            LEFT JOIN market_snapshots_daily ms ON ms.stock_code = s.code AND ms.trade_date = ?
            LEFT JOIN stock_industry_map im ON im.stock_code = s.code AND im.effective_date = ?
            WHERE COALESCE(s.is_suspended, 0) = 0
            """,
            (trade_date, trade_date, trade_date),
        ).fetchall()
    result = []
    for row in dicts_from_rows(rows):
        code = row["code"]
        pct = float(row.get("pctChange") or 0)
        close = float(row.get("close") or 0)
        limit_up_price = float(row.get("limitUpPrice") or 0)
        limit_down_price = float(row.get("limitDownPrice") or 0)
        limit_rate = _limit_rate(code, row.get("name") or "")
        is_limit_up = bool(row.get("snapshotLimitUp")) or (close > 0 and ((limit_up_price > 0 and close >= limit_up_price * 0.995) or pct >= limit_rate * 100 - 0.15))
        is_limit_down = bool(row.get("snapshotLimitDown")) or (close > 0 and ((limit_down_price > 0 and close <= limit_down_price * 1.005) or pct <= -limit_rate * 100 + 0.15))
        sw_l1 = row.get("swL1Name") or "综合"
        sw_l2 = row.get("swL2Name") or sw_l1
        result.append(
            {
                "code": code,
                "name": row.get("name") or code,
                "industry": sw_l1,
                "swL1Name": sw_l1,
                "swL2Name": sw_l2,
                "swL3Name": row.get("swL3Name") or "",
                "market": row.get("market") or infer_market(code),
                "isST": bool(row.get("isST")),
                "open": _num(row.get("open")),
                "high": _num(row.get("high")),
                "low": _num(row.get("low")),
                "close": close,
                "pctChange": pct,
                "amount": _num(row.get("amount")),
                "turnoverRate": row.get("turnoverRate"),
                "floatMarketCap": _num(row.get("floatMarketCap")),
                "limitUpPrice": limit_up_price or round(close / (1 + pct / 100) * (1 + limit_rate), 2) if close and pct > -99 else limit_up_price,
                "limitDownPrice": limit_down_price,
                "isLimitUp": is_limit_up,
                "isLimitDown": is_limit_down,
                "isBrokenBoard": bool(row.get("isBrokenBoard")),
                "firstLimitTime": row.get("firstLimitTime"),
                "lastLimitTime": row.get("lastLimitTime"),
                "openBoardCount": int(row.get("openBoardCount") or 0),
                "sealAmount": _num(row.get("sealAmount")),
                "sealAmountRatio": _num(row.get("sealAmountRatio")),
                "limitUpType": row.get("limitUpType") or "未知",
                "snapshotIsNewHigh": bool(row.get("snapshotIsNewHigh")),
            }
        )
    return result


def _group_limit_rows(trade_date: str, rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    heights = _board_heights(trade_date, rows)
    for row in rows:
        height = heights.get(row["code"], 1)
        grouped[max(1, height)].append(row)
    for group_rows in grouped.values():
        group_rows.sort(key=lambda item: -(float(item.get("amount") or 0)))
    return grouped


def _board_heights(trade_date: str, rows: list[dict[str, Any]]) -> dict[str, int]:
    current_codes = {row["code"] for row in rows}
    heights = {code: 1 for code in current_codes}
    remaining = set(current_codes)
    if not remaining:
        return heights
    for day in _trading_days_until(trade_date, limit=20)[1:]:
        previous_limit_codes = {row["code"] for row in _limit_up_rows(day) if row["isLimitUp"]}
        for code in list(remaining):
            if code in previous_limit_codes:
                heights[code] += 1
            else:
                remaining.remove(code)
        if not remaining:
            break
    return heights


def _trading_days_until(trade_date: str, limit: int = 20) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date AS trade_date FROM daily_prices WHERE date <= ?
            UNION
            SELECT trade_date FROM market_snapshots_daily WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (trade_date, trade_date, limit),
        ).fetchall()
    return [row["trade_date"] for row in rows]


def _resolve_stats_date(trade_date: str | None) -> str:
    if trade_date:
        return trade_date
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(trade_date) AS trade_date FROM market_snapshots_daily
            UNION SELECT MAX(date) AS trade_date FROM daily_prices
            ORDER BY trade_date DESC LIMIT 1
            """
        ).fetchone()
    return row["trade_date"] if row and row["trade_date"] else target_trade_date()


def _snapshot_updated_at(trade_date: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(updated_at) AS updated_at FROM market_snapshots_daily WHERE trade_date = ?", (trade_date,)).fetchone()
    return row["updated_at"] if row and row["updated_at"] else None


def _build_limit_up_summary(trade_date: str, rows: list[dict[str, Any]], grouped: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    height_distribution = [
        {"height": height, "count": len(items), "label": _height_label(height)}
        for height, items in sorted(grouped.items(), key=lambda item: item[0], reverse=True)
    ]
    limit_up_count = sum(1 for row in rows if row["isLimitUp"])
    highest = max(grouped.keys(), default=0)
    return {
        "tradeDate": trade_date,
        "updatedAt": _snapshot_updated_at(trade_date),
        "limitUpCount": limit_up_count,
        "limitDownCount": sum(1 for row in rows if row["isLimitDown"]),
        "brokenLimitCount": 0,
        "boardStockCount": sum(len(items) for height, items in grouped.items() if height >= 2),
        "highestBoard": highest,
        "firstBoardCount": len(grouped.get(1, [])),
        "secondBoardCount": len(grouped.get(2, [])),
        "thirdPlusCount": sum(len(items) for height, items in grouped.items() if height >= 3),
        "heightDistribution": height_distribution,
        "dataWarning": _stats_data_warning(trade_date),
    }


def _stats_data_warning(trade_date: str) -> str | None:
    days = _trading_days_until(trade_date, limit=4)
    if len(days) < 3:
        return "历史行情不足，连板统计可能不完整。"
    status = get_market_data_sync_status(trade_date)
    if status.get("isRunning"):
        return "今日行情数据同步中，当前展示上一交易日或已缓存结果。"
    if status.get("needsSync"):
        return "今日行情尚未完成同步，当前结果可能来自上一交易日缓存。"
    return None


def _new_high_map(rows: list[dict[str, Any]], trade_date: str) -> dict[str, bool]:
    codes = sorted({row["code"] for row in rows})
    if not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    with get_connection() as conn:
        high_rows = conn.execute(
            f"""
            SELECT stock_code, MAX(high) AS high120
            FROM daily_prices
            WHERE date <= ? AND stock_code IN ({placeholders})
            GROUP BY stock_code
            """,
            (trade_date, *codes),
        ).fetchall()
    high_map = {row["stock_code"]: float(row["high120"] or 0) for row in high_rows}
    return {
        row["code"]: bool(row.get("close") and high_map.get(row["code"]) and float(row["close"]) >= high_map[row["code"]] * 0.995)
        for row in rows
    }



def _sample_snapshot_rows(limit: int | None = None) -> list[dict[str, Any]]:
    target = _resolve_stats_date(None)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.code, s.name, s.industry, s.market, s.is_st, s.is_suspended, s.float_market_cap,
                   dp.open, dp.high, dp.low, dp.close, dp.volume, dp.amount, dp.pct_change
            FROM stocks s
            JOIN daily_prices dp ON dp.stock_code = s.code
             AND dp.date = (SELECT MAX(date) FROM daily_prices WHERE stock_code = s.code)
            ORDER BY s.code
            LIMIT ?
            """,
            (limit or 100000,),
        ).fetchall()
    result = []
    for row in dicts_from_rows(rows):
        limit_rate = _limit_rate(row["code"], row["name"])
        close = float(row["close"] or 0)
        pct = float(row["pct_change"] or 0)
        pre_close = close / (1 + pct / 100) if close and pct > -99 else close
        result.append(
            {
                "stock_code": row["code"],
                "stock_name": row["name"],
                "industry": row["industry"],
                "market": row["market"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": close,
                "pre_close": pre_close,
                "change_pct": pct,
                "volume": row["volume"],
                "amount": row["amount"],
                "turnover_rate": None,
                "market_value": row["float_market_cap"],
                "float_market_value": row["float_market_cap"],
                "limit_up_price": round(pre_close * (1 + limit_rate), 2),
                "limit_down_price": round(pre_close * (1 - limit_rate), 2),
                "is_limit_up": pct >= limit_rate * 100 - 0.15,
                "is_limit_down": pct <= -limit_rate * 100 + 0.15,
                "is_suspended": bool(row["is_suspended"]),
                "is_st": bool(row["is_st"]),
                "raw_json": "{}",
            }
        )
    return result


def _match_height_filter(height: int, height_filter: str, highest: int) -> bool:
    if height_filter == "first":
        return height == 1
    if height_filter == "2":
        return height == 2
    if height_filter == "3plus":
        return height >= 3
    if height_filter == "highest":
        return height == highest
    return True


def _match_market_filter(code: str, market_filter: str) -> bool:
    if market_filter == "main":
        return code.startswith(("00", "60")) and not code.startswith(("688", "689"))
    if market_filter == "cyb":
        return code.startswith(("300", "301"))
    if market_filter == "kc":
        return code.startswith(("688", "689"))
    if market_filter == "bj":
        return code.startswith(("8", "4"))
    return True


def _height_label(height: int) -> str:
    return "首板" if height <= 1 else f"{height}连板"


def _limit_rate(code: str, name: str = "") -> float:
    if "ST" in name.upper():
        return 0.05
    if code.startswith(("300", "301", "688", "689")):
        return 0.20
    if code.startswith(("8", "4")):
        return 0.30
    return 0.10


def _num(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if number != number else number


def _notify(progress_callback: ProgressCallback | None, progress: int, message: str) -> None:
    if progress_callback:
        progress_callback(progress, message)
