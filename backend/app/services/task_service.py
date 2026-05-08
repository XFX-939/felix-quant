from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso

RUNNING_STATUSES = {"pending", "running"}


def create_task_run(
    task_type: str,
    trade_date: str | None = None,
    total_count: int = 0,
    created_by: str = "system",
    current_stage: str = "pending",
    parent_task_id: int | None = None,
    child_task_count: int = 0,
    batch_mode: bool = False,
    strategy_name: str | None = None,
    task_group_name: str | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO task_runs (
                task_type, trade_date, status, current_stage, total_count,
                processed_count, success_count, failed_count, retry_count,
                progress_percent, started_at, summary_json, created_by, created_at, updated_at,
                parent_task_id, child_task_count, completed_child_count, failed_child_count,
                batch_mode, strategy_name, task_group_name
            )
            VALUES (?, ?, 'running', ?, ?, 0, 0, 0, 0, 0, ?, '{}', ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
            """,
            (
                task_type,
                trade_date,
                current_stage,
                int(total_count or 0),
                timestamp,
                created_by,
                timestamp,
                timestamp,
                parent_task_id,
                int(child_task_count or 0),
                1 if batch_mode else 0,
                strategy_name,
                task_group_name,
            ),
        )
        task_id = int(cursor.lastrowid)
    return get_task_run(task_id) or {}


def find_running_task(task_type: str, trade_date: str | None = None) -> dict[str, Any] | None:
    params: list[Any] = [task_type, *RUNNING_STATUSES]
    date_clause = "trade_date IS ?" if trade_date is None else "trade_date = ?"
    params.append(trade_date)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT *
            FROM task_runs
            WHERE task_type = ?
              AND status IN (?, ?)
              AND {date_clause}
            ORDER BY id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    return _decode_task(row)


def get_task_run(task_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM task_runs WHERE id = ?", (task_id,)).fetchone()
    return _decode_task(row)


def list_task_runs(limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM task_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit or 20),),
        ).fetchall()
    return [_decode_task(row) for row in rows if row is not None]


def list_child_task_runs(parent_task_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM task_runs
            WHERE parent_task_id = ?
            ORDER BY id ASC
            """,
            (parent_task_id,),
        ).fetchall()
    return [_decode_task(row) for row in rows if row is not None]


def update_task_run(task_id: int, **changes: Any) -> dict[str, Any]:
    allowed = {
        "status",
        "current_stage",
        "total_count",
        "processed_count",
        "success_count",
        "failed_count",
        "retry_count",
        "progress_percent",
        "error_message",
        "summary_json",
        "parent_task_id",
        "child_task_count",
        "completed_child_count",
        "failed_child_count",
        "batch_mode",
        "strategy_name",
        "task_group_name",
    }
    task = get_task_run(task_id)
    if not task:
        return {}
    values = {key: value for key, value in changes.items() if key in allowed}
    if "summary_json" in values and not isinstance(values["summary_json"], str):
        values["summary_json"] = json.dumps(values["summary_json"], ensure_ascii=False)
    total = int(values.get("total_count", task.get("total_count") or 0) or 0)
    processed = int(values.get("processed_count", task.get("processed_count") or 0) or 0)
    if "progress_percent" not in values and total > 0:
        values["progress_percent"] = round(min(99, max(0, processed / total * 100)), 2)
    values["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in values)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE task_runs SET {assignments} WHERE id = ?",
            [*values.values(), task_id],
        )
    return get_task_run(task_id) or {}


def finish_task_run(
    task_id: int,
    status: str = "success",
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    task = get_task_run(task_id)
    if not task:
        return {}
    finished_at = now_iso()
    duration_ms = _duration_ms(task.get("started_at"), finished_at)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE task_runs
            SET status = ?,
                progress_percent = CASE WHEN ? IN ('success', 'partial_success') THEN 100 ELSE progress_percent END,
                finished_at = ?,
                duration_ms = ?,
                error_message = ?,
                summary_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                status,
                finished_at,
                duration_ms,
                error_message,
                json.dumps(summary or {}, ensure_ascii=False),
                finished_at,
                task_id,
            ),
        )
    return get_task_run(task_id) or {}


def record_failed_sync(
    trade_date: str,
    code: str,
    name: str,
    task_type: str,
    data_type: str,
    status: str,
    retry_count: int,
    max_retries: int,
    error_message: str,
    raw_context: dict[str, Any] | None = None,
    next_retry_at: str | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    payload = json.dumps(raw_context or {}, ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO failed_sync_records (
                trade_date, code, name, task_type, data_type, status, retry_count, max_retries,
                error_message, last_error_at, next_retry_at, raw_context_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, code, task_type, data_type) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                retry_count = excluded.retry_count,
                max_retries = excluded.max_retries,
                error_message = excluded.error_message,
                last_error_at = excluded.last_error_at,
                next_retry_at = excluded.next_retry_at,
                raw_context_json = excluded.raw_context_json,
                updated_at = excluded.updated_at
            """,
            (
                trade_date,
                code,
                name,
                task_type,
                data_type,
                status,
                int(retry_count or 0),
                int(max_retries or 3),
                error_message,
                timestamp,
                next_retry_at,
                payload,
                timestamp,
                timestamp,
            ),
        )
    return _find_failed_record(trade_date, code, task_type, data_type) or {}


def mark_sync_recovered(trade_date: str, code: str, task_type: str, data_type: str) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE failed_sync_records
            SET status = 'recovered', updated_at = ?
            WHERE trade_date = ? AND code = ? AND task_type = ? AND data_type = ?
            """,
            (timestamp, trade_date, code, task_type, data_type),
        )


def list_failed_sync_records(
    task_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if task_type:
        clauses.append("task_type = ?")
        params.append(task_type)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM failed_sync_records
            {where_sql}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            [*params, int(limit or 50)],
        ).fetchall()
    return [_decode_failed_record(row) for row in rows]


def pending_failed_stock_codes(trade_date: str | None = None, task_type: str = "sync_stock_daily") -> list[str]:
    params: list[Any] = [task_type]
    clauses = ["task_type = ?", "data_type = 'stock_daily'", "status IN ('pending', 'retrying', 'failed')"]
    if trade_date:
        clauses.append("trade_date = ?")
        params.append(trade_date)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT code
            FROM failed_sync_records
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at ASC
            """,
            params,
        ).fetchall()
    return [row["code"] for row in rows]


def _find_failed_record(trade_date: str, code: str, task_type: str, data_type: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM failed_sync_records
            WHERE trade_date = ? AND code = ? AND task_type = ? AND data_type = ?
            """,
            (trade_date, code, task_type, data_type),
        ).fetchone()
    return _decode_failed_record(row)


def _decode_task(row: Any) -> dict[str, Any] | None:
    item = dict_from_row(row)
    if not item:
        return None
    item["summary_json"] = _json_loads(item.get("summary_json"), {})
    return item


def _decode_failed_record(row: Any) -> dict[str, Any]:
    item = dict_from_row(row) or {}
    item["raw_context_json"] = _json_loads(item.get("raw_context_json"), {})
    return item


def _json_loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _duration_ms(started_at: str | None, finished_at: str) -> int:
    if not started_at:
        return 0
    try:
        start = datetime.fromisoformat(started_at)
        finish = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0
    return max(0, int((finish - start).total_seconds() * 1000))
