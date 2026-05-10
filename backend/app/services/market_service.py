from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta
from typing import Callable

import numpy as np

from app.core.config import AKSHARE_ADJUST, AKSHARE_HISTORY_DAYS, AKSHARE_STOCK_SCOPE, AKSHARE_SYNC_INDUSTRY, MARKET_DATA_SOURCE
from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso, refresh_sample_market_shape
from app.services.akshare_provider import AkshareDataProvider, AkshareUnavailableError, normalize_stock_code
from app.services.analytics import enrich_prices
from app.services import task_service

ProgressCallback = Callable[[int, str], None]
SYNC_MAX_RETRIES = 3
SYNC_RETRY_DELAYS_SECONDS = [2, 5, 10]
SYNC_FAILURE_RATE_LIMIT = 0.25


def list_stocks(search: str | None = None, industry: str | None = None) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if search:
        clauses.append("(s.code LIKE ? OR s.name LIKE ?)")
        keyword = f"%{search}%"
        params.extend([keyword, keyword])
    if industry and industry != "all":
        clauses.append("s.industry = ?")
        params.append(industry)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                s.*,
                COALESCE(ms.trade_date, dp.date) AS price_date,
                COALESCE(ms.close, dp.close) AS current_price,
                COALESCE(ms.change_pct, dp.pct_change) AS pct_change
            FROM stocks s
            LEFT JOIN daily_prices dp
                ON dp.stock_code = s.code
               AND dp.date = (SELECT MAX(date) FROM daily_prices WHERE stock_code = s.code)
            LEFT JOIN market_snapshots_daily ms
                ON ms.stock_code = s.code
               AND ms.trade_date = (SELECT MAX(trade_date) FROM market_snapshots_daily)
            {where_sql}
            ORDER BY s.code
            """,
            params,
        ).fetchall()
    return dicts_from_rows(rows)


def get_stock(code: str) -> dict | None:
    with get_connection() as conn:
        stock = conn.execute(
            """
            SELECT
                s.*,
                COALESCE(ms.trade_date, dp.date) AS price_date,
                COALESCE(ms.open, dp.open) AS open,
                COALESCE(ms.high, dp.high) AS high,
                COALESCE(ms.low, dp.low) AS low,
                COALESCE(ms.close, dp.close) AS current_price,
                COALESCE(ms.volume, dp.volume) AS volume,
                COALESCE(ms.amount, dp.amount) AS amount,
                COALESCE(ms.change_pct, dp.pct_change) AS pct_change
            FROM stocks s
            LEFT JOIN daily_prices dp
                ON dp.stock_code = s.code
               AND dp.date = (SELECT MAX(date) FROM daily_prices WHERE stock_code = s.code)
            LEFT JOIN market_snapshots_daily ms
                ON ms.stock_code = s.code
               AND ms.trade_date = (SELECT MAX(trade_date) FROM market_snapshots_daily)
            WHERE s.code = ?
            """,
            (code,),
        ).fetchone()
        if not stock:
            return None
        prices = get_prices(code, limit=180)
        enriched = enrich_prices(prices)
        latest = enriched.iloc[-1].to_dict() if not enriched.empty else {}
        signal = conn.execute(
            """
            SELECT sig.*, st.name AS strategy_name
            FROM signals sig
            JOIN strategies st ON st.id = sig.strategy_id
            WHERE sig.stock_code = ?
            ORDER BY sig.date DESC, sig.score DESC
            LIMIT 1
            """,
            (code,),
        ).fetchone()
    result = dict_from_row(stock) or {}
    result["indicators"] = {
        "ma20": _round(latest.get("ma20")),
        "ma60": _round(latest.get("ma60")),
        "ret20": _round(latest.get("ret20")),
        "ret60": _round(latest.get("ret60")),
        "volatility_60": _round(latest.get("volatility_60")),
        "max_drawdown_60": _round(latest.get("max_drawdown_60")),
    }
    result["latest_signal"] = dict_from_row(signal)
    return result


def get_prices(code: str, limit: int | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    clauses = ["stock_code = ?"]
    params: list[object] = [code]
    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)
    limit_sql = "LIMIT ?" if limit else ""
    if limit:
        params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT stock_code, date, open, high, low, close, volume, amount, pct_change
            FROM daily_prices
            WHERE {' AND '.join(clauses)}
            ORDER BY date DESC
            {limit_sql}
            """,
            params,
        ).fetchall()
    data = dicts_from_rows(rows)
    return list(reversed(data))


def list_industries() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT industry FROM stocks ORDER BY industry").fetchall()
    return [row["industry"] for row in rows]


def latest_trade_date() -> str | None:
    latest_allowed = _latest_business_day(date.today()).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(trade_date) AS latest_date
            FROM (
                SELECT MAX(date) AS trade_date FROM daily_prices WHERE date <= ?
                UNION
                SELECT MAX(trade_date) AS trade_date FROM market_snapshots_daily WHERE trade_date <= ?
            )
            """,
            (latest_allowed, latest_allowed),
        ).fetchone()
    return row["latest_date"] if row and row["latest_date"] else None


def update_market_data(
    source: str | None = None,
    scope: str | None = None,
    limit: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    data_source = (source or MARKET_DATA_SOURCE or "akshare").lower()
    if data_source == "sample":
        return _update_sample_market_data()
    if data_source == "akshare":
        try:
            return _update_akshare_market_data(scope=scope, limit=limit, progress_callback=progress_callback)
        except AkshareUnavailableError as exc:
            if source:
                raise
            result = _update_sample_market_data()
            result["fallback_reason"] = str(exc)
            return result
    raise ValueError(f"不支持的数据源：{data_source}")


def _update_sample_market_data() -> dict:
    target = _latest_business_day(date.today())
    updated_rows = 0
    refreshed_rows = 0
    timestamp = now_iso()
    rng = np.random.default_rng(target.toordinal())

    with get_connection() as conn:
        stocks = conn.execute("SELECT code FROM stocks ORDER BY code").fetchall()
        for idx, stock in enumerate(stocks):
            code = stock["code"]
            last = conn.execute(
                "SELECT * FROM daily_prices WHERE stock_code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
            if not last:
                continue
            last_date = datetime.fromisoformat(last["date"]).date()
            business_days = _business_days(last_date + timedelta(days=1), target)
            if not business_days:
                _refresh_latest_price(conn, code, last, idx, rng)
                refreshed_rows += 1
            for day in business_days:
                _insert_simulated_price(conn, code, last, day, idx, rng)
                updated_rows += 1
                last = conn.execute(
                    "SELECT * FROM daily_prices WHERE stock_code = ? AND date = ?",
                    (code, day.isoformat()),
                ).fetchone()
            conn.execute("UPDATE stocks SET updated_at = ? WHERE code = ?", (timestamp, code))

    refresh_sample_market_shape()
    return {
        "source": "sample",
        "updated_rows": updated_rows,
        "refreshed_rows": refreshed_rows,
        "trade_date": target.isoformat(),
        "updated_at": timestamp,
    }


def _update_akshare_market_data(
    scope: str | None = None,
    limit: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    stock_scope = (scope or AKSHARE_STOCK_SCOPE or "tracked").lower()
    if stock_scope not in {"tracked", "all", "failed"}:
        raise ValueError("AKShare 股票范围仅支持 tracked、all 或 failed")

    provider = AkshareDataProvider(include_industry=AKSHARE_SYNC_INDUSTRY)
    timestamp = now_iso()
    end = _latest_business_day(date.today())
    end_date = end.strftime("%Y%m%d")

    if stock_scope == "failed":
        _notify_progress(progress_callback, 9, "正在读取失败补抓股票列表")
        existing_by_code = _existing_stock_metadata()
        failed_codes = task_service.pending_failed_stock_codes(task_type="sync_stock_daily")
        if limit:
            failed_codes = failed_codes[:limit]
        universe = _fallback_existing_stocks(failed_codes, existing_by_code)
    elif stock_scope == "tracked":
        _notify_progress(progress_callback, 9, "正在读取本地跟踪股票列表")
        existing_by_code = _existing_stock_metadata()
        tracked_codes = _tracked_stock_codes()
        if limit:
            tracked_codes = tracked_codes[:limit]
        universe = _fallback_existing_stocks(tracked_codes, existing_by_code)
    else:
        try:
            _notify_progress(progress_callback, 9, "正在从 AKShare 获取全市场股票列表")
            universe = provider.fetch_stock_universe(limit=limit)
        except Exception as exc:
            raise AkshareUnavailableError(f"AKShare 股票列表同步失败：{exc}") from exc
    if not universe:
        if stock_scope == "failed":
            return {
                "source": "akshare",
                "scope": stock_scope,
                "adjust": AKSHARE_ADJUST or "不复权",
                "stock_count": 0,
                "price_rows": 0,
                "skipped_count": 0,
                "pruned_future_rows": 0,
                "failed_count": 0,
                "retry_count": 0,
                "failed": [],
                "trade_date": end.isoformat(),
                "start_date": end.isoformat(),
                "end_date": end.isoformat(),
                "updated_at": timestamp,
            }
        raise AkshareUnavailableError("AKShare 未返回可同步股票，请稍后重试或检查网络。")
    universe = _prioritize_failed_stocks(universe, end.isoformat())
    _notify_progress(progress_callback, 12, f"已获取 {len(universe)} 只股票，正在写入股票基础信息")

    upserted_stocks = 0
    inserted_prices = 0
    skipped_stocks = 0
    total_retry_count = 0
    pruned_future_rows = 0
    failed: list[dict[str, str]] = []
    latest_synced_date = ""
    earliest_requested_date = ""
    stop_reason: str | None = None
    processed_stocks = 0
    with get_connection() as conn:
        for stock in universe:
            _upsert_stock(conn, stock, timestamp)
            upserted_stocks += 1

    total = len(universe)
    for index, stock in enumerate(universe, start=1):
        processed_stocks = index
        code = stock["code"]
        name = stock.get("name") or code
        progress = 12 + int(index / max(total, 1) * 83)
        _notify_progress(progress_callback, progress, f"正在同步日线 {index}/{total}：{code} {name}")
        sync_window = _daily_sync_window(code, end)
        if sync_window is None:
            skipped_stocks += 1
            continue
        start_date, stock_end_date = sync_window
        if not earliest_requested_date or start_date < earliest_requested_date:
            earliest_requested_date = start_date
        try:
            prices, retry_count = _fetch_daily_prices_with_retry(
                provider,
                code=code,
                start_date=start_date,
                end_date=stock_end_date,
                adjust=AKSHARE_ADJUST,
            )
        except Exception as exc:
            total_retry_count += SYNC_MAX_RETRIES
            failed.append({"code": code, "reason": str(exc)[:180]})
            _record_stock_sync_failure(end.isoformat(), stock, str(exc)[:300], SYNC_MAX_RETRIES)
            stop_reason = _failure_rate_stop_reason(index, len(failed), total)
            if stop_reason:
                _notify_progress(progress_callback, progress, stop_reason)
                break
            continue
        total_retry_count += retry_count
        if not prices:
            failed.append({"code": code, "reason": "AKShare 未返回日线行情"})
            _record_stock_sync_failure(end.isoformat(), stock, "AKShare 未返回日线行情", retry_count)
            stop_reason = _failure_rate_stop_reason(index, len(failed), total)
            if stop_reason:
                _notify_progress(progress_callback, progress, stop_reason)
                break
            continue
        with get_connection() as conn:
            for price in prices:
                _upsert_daily_price(conn, price)
                inserted_prices += 1
                if price["date"] > latest_synced_date:
                    latest_synced_date = price["date"]
            first_date = prices[0]["date"]
            conn.execute(
                """
                UPDATE stocks
                SET list_date = COALESCE(list_date, ?), updated_at = ?
                WHERE code = ?
                """,
                (first_date, timestamp, code),
            )
        _mark_stock_sync_success(code, latest_synced_date or prices[-1]["date"], timestamp)
        task_service.mark_sync_recovered(end.isoformat(), code, "sync_stock_daily", "stock_daily")
    _notify_progress(progress_callback, 96, "正在清理异常未来日期行情")
    with get_connection() as conn:
        if latest_synced_date:
            cursor = conn.execute("DELETE FROM daily_prices WHERE date > ?", (latest_synced_date,))
            pruned_future_rows = cursor.rowcount

    return {
        "source": "akshare",
        "scope": stock_scope,
        "adjust": AKSHARE_ADJUST or "不复权",
        "stock_count": upserted_stocks,
        "price_rows": inserted_prices,
        "skipped_count": skipped_stocks,
        "pruned_future_rows": pruned_future_rows,
        "failed_count": len(failed),
        "retry_count": total_retry_count,
        "failed": failed[:20],
        "failure_rate": round(len(failed) / max(processed_stocks, 1), 4),
        "stopped_early": bool(stop_reason),
        "stop_reason": stop_reason,
        "trade_date": latest_synced_date or end.isoformat(),
        "start_date": earliest_requested_date or end.isoformat(),
        "end_date": end.isoformat(),
        "updated_at": timestamp,
    }


def _fetch_daily_prices_with_retry(
    provider: AkshareDataProvider,
    code: str,
    start_date: str,
    end_date: str,
    adjust: str,
    sleep_fn: Callable[[int], None] = time.sleep,
) -> tuple[list[dict], int]:
    last_exc: Exception | None = None
    for attempt in range(SYNC_MAX_RETRIES + 1):
        try:
            return provider.fetch_daily_prices(code, start_date=start_date, end_date=end_date, adjust=adjust), attempt
        except Exception as exc:  # noqa: BLE001 - remote data providers raise inconsistent exception types
            last_exc = exc
            if attempt >= SYNC_MAX_RETRIES:
                break
            sleep_fn(SYNC_RETRY_DELAYS_SECONDS[attempt])
    assert last_exc is not None
    raise last_exc


def _failure_rate_stop_reason(processed_count: int, failed_count: int, total_count: int) -> str | None:
    if processed_count <= 0:
        return None
    minimum_sample = min(20, total_count)
    if processed_count < minimum_sample:
        return None
    failure_rate = failed_count / processed_count
    if failure_rate <= SYNC_FAILURE_RATE_LIMIT:
        return None
    return (
        f"失败率 {failure_rate:.0%} 超过 {SYNC_FAILURE_RATE_LIMIT:.0%} 阈值，"
        "已暂停本轮同步，可能触发上游限流或网络异常。"
    )


def _daily_sync_window(code: str, end: date) -> tuple[str, str] | None:
    end_iso = end.isoformat()
    with get_connection() as conn:
        state = conn.execute("SELECT last_daily_date FROM stock_sync_state WHERE code = ?", (code,)).fetchone()
        latest_price = conn.execute("SELECT MAX(date) AS latest_date FROM daily_prices WHERE stock_code = ?", (code,)).fetchone()
    last_daily_date = (state["last_daily_date"] if state and state["last_daily_date"] else None) or (latest_price["latest_date"] if latest_price else None)
    if last_daily_date and last_daily_date >= end_iso:
        return None
    if last_daily_date:
        start = datetime.fromisoformat(last_daily_date).date() + timedelta(days=1)
    else:
        start = end - timedelta(days=max(30, int(min(AKSHARE_HISTORY_DAYS, 250) * 1.8)))
    if start > end:
        return None
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _mark_stock_sync_success(code: str, last_daily_date: str, timestamp: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stock_sync_state (
                code, last_daily_date, last_success_at, failed_count, last_error_message, status, updated_at
            )
            VALUES (?, ?, ?, 0, NULL, 'success', ?)
            ON CONFLICT(code) DO UPDATE SET
                last_daily_date = CASE
                    WHEN stock_sync_state.last_daily_date IS NULL OR excluded.last_daily_date > stock_sync_state.last_daily_date
                    THEN excluded.last_daily_date
                    ELSE stock_sync_state.last_daily_date
                END,
                last_success_at = excluded.last_success_at,
                failed_count = 0,
                last_error_message = NULL,
                status = 'success',
                updated_at = excluded.updated_at
            """,
            (code, last_daily_date, timestamp, timestamp),
        )


def _record_stock_sync_failure(trade_date: str, stock: dict, error_message: str, retry_count: int) -> None:
    timestamp = now_iso()
    code = stock["code"]
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stock_sync_state (
                code, failed_count, last_error_message, status, updated_at
            )
            VALUES (?, 1, ?, 'failed', ?)
            ON CONFLICT(code) DO UPDATE SET
                failed_count = stock_sync_state.failed_count + 1,
                last_error_message = excluded.last_error_message,
                status = 'failed',
                updated_at = excluded.updated_at
            """,
            (code, error_message, timestamp),
        )
    task_service.record_failed_sync(
        trade_date=trade_date,
        code=code,
        name=stock.get("name") or code,
        task_type="sync_stock_daily",
        data_type="stock_daily",
        status="failed",
        retry_count=retry_count,
        max_retries=SYNC_MAX_RETRIES,
        error_message=error_message,
        raw_context={"source": "akshare", "adjust": AKSHARE_ADJUST or "不复权"},
    )


def _prioritize_failed_stocks(universe: list[dict], trade_date: str) -> list[dict]:
    failed_codes = task_service.pending_failed_stock_codes(trade_date=trade_date, task_type="sync_stock_daily")
    if not failed_codes:
        failed_codes = task_service.pending_failed_stock_codes(task_type="sync_stock_daily")
    if not failed_codes:
        return universe
    priority = {code: index for index, code in enumerate(failed_codes)}
    return sorted(universe, key=lambda stock: priority.get(stock["code"], len(priority) + 1))


def _notify_progress(progress_callback: ProgressCallback | None, progress: int, message: str) -> None:
    if progress_callback:
        progress_callback(progress, message)


def _insert_simulated_price(conn, code: str, last, day: date, idx: int, rng: np.random.Generator) -> None:
    close_prev = float(last["close"])
    volatility = 0.012 + (idx % 5) * 0.003
    drift = 0.0005 + (idx % 4) * 0.0001
    shock = rng.normal(drift + math.sin(day.toordinal() / 17 + idx) * 0.004, volatility)
    open_price = max(1.0, close_prev * (1 + rng.normal(0, volatility / 3)))
    close = max(1.0, open_price * (1 + shock))
    high = max(open_price, close) * (1 + abs(rng.normal(0.007, 0.003)))
    low = min(open_price, close) * (1 - abs(rng.normal(0.007, 0.003)))
    volume = max(100000, float(last["volume"]) * (1 + rng.normal(0, 0.08)))
    pct_change = (close - close_prev) / close_prev * 100
    conn.execute(
        """
        INSERT OR REPLACE INTO daily_prices
            (stock_code, date, open, high, low, close, volume, amount, pct_change)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            code,
            day.isoformat(),
            round(open_price, 2),
            round(high, 2),
            round(low, 2),
            round(close, 2),
            round(volume, 0),
            round(volume * close, 2),
            round(pct_change, 2),
        ),
    )


def _refresh_latest_price(conn, code: str, last, idx: int, rng: np.random.Generator) -> None:
    volatility = 0.004 + (idx % 4) * 0.001
    close_prev = float(last["close"])
    close = max(1.0, close_prev * (1 + rng.normal(0, volatility)))
    pct_change = float(last["pct_change"]) + (close - close_prev) / close_prev * 100
    volume = max(100000, float(last["volume"]) * (1 + rng.normal(0, 0.025)))
    conn.execute(
        """
        UPDATE daily_prices
        SET close = ?, high = MAX(high, ?), low = MIN(low, ?), volume = ?, amount = ?, pct_change = ?
        WHERE id = ?
        """,
        (
            round(close, 2),
            round(close, 2),
            round(close, 2),
            round(volume, 0),
            round(volume * close, 2),
            round(pct_change, 2),
            last["id"],
        ),
    )


def _business_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _latest_business_day(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _tracked_stock_codes() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT code FROM stocks ORDER BY code").fetchall()
    return [normalize_stock_code(row["code"]) for row in rows]


def _existing_stock_metadata() -> dict[str, dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT code, name, industry, market, list_date, is_st, is_suspended, float_market_cap FROM stocks").fetchall()
    return {normalize_stock_code(row["code"]): dict_from_row(row) or {} for row in rows}


def _merge_existing_stock_metadata(stock: dict, existing: dict | None) -> dict:
    if not existing:
        return stock
    merged = dict(stock)
    if merged.get("industry") == "未分类" and existing.get("industry"):
        merged["industry"] = existing["industry"]
    merged["list_date"] = existing.get("list_date")
    return merged


def _fallback_existing_stocks(codes: list[str], existing_by_code: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for code in codes:
        existing = existing_by_code.get(code)
        if not existing:
            continue
        rows.append(
            {
                "code": normalize_stock_code(existing.get("code")),
                "name": existing.get("name") or code,
                "industry": existing.get("industry") or "未分类",
                "market": existing.get("market") or ("SH" if code.startswith("6") else "SZ"),
                "list_date": existing.get("list_date"),
                "is_st": bool(existing.get("is_st")),
                "is_suspended": bool(existing.get("is_suspended")),
                "float_market_cap": float(existing.get("float_market_cap") or 8000000000),
            }
        )
    return rows


def _upsert_stock(conn, stock: dict, timestamp: str) -> None:
    conn.execute(
        """
        INSERT INTO stocks
            (code, name, industry, market, list_date, is_st, is_suspended, float_market_cap, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name = excluded.name,
            industry = excluded.industry,
            market = excluded.market,
            list_date = COALESCE(stocks.list_date, excluded.list_date),
            is_st = excluded.is_st,
            is_suspended = excluded.is_suspended,
            float_market_cap = excluded.float_market_cap,
            updated_at = excluded.updated_at
        """,
        (
            stock["code"],
            stock["name"],
            stock.get("industry") or "未分类",
            stock.get("market") or "SZ",
            stock.get("list_date"),
            1 if stock.get("is_st") else 0,
            1 if stock.get("is_suspended") else 0,
            float(stock.get("float_market_cap") or 8000000000),
            timestamp,
            timestamp,
        ),
    )


def _upsert_daily_price(conn, price: dict) -> None:
    conn.execute(
        """
        INSERT INTO daily_prices
            (stock_code, date, open, high, low, close, volume, amount, pct_change)
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
        (
            price["stock_code"],
            price["date"],
            price["open"],
            price["high"],
            price["low"],
            price["close"],
            price["volume"],
            price["amount"],
            price["pct_change"],
        ),
    )


def _round(value: object, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return round(number, digits)
