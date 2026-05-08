from __future__ import annotations

import json
from typing import Any

from app.db.database import dict_from_row, dicts_from_rows, get_connection, now_iso


def list_reviews(date: str | None = None, stock_code: str | None = None, tag: str | None = None, limit: int = 100) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if date:
        clauses.append("r.date = ?")
        params.append(date)
    if stock_code:
        clauses.append("(r.stock_code LIKE ? OR s.name LIKE ?)")
        keyword = f"%{stock_code}%"
        params.extend([keyword, keyword])
    if tag and tag != "all":
        clauses.append("r.tags LIKE ?")
        params.append(f"%{tag}%")
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT r.*, s.name AS stock_name, sig.reason AS signal_reason
            FROM reviews r
            JOIN stocks s ON s.code = r.stock_code
            LEFT JOIN signals sig ON sig.id = r.signal_id
            {where_sql}
            ORDER BY r.date DESC, r.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    reviews = dicts_from_rows(rows)
    for review in reviews:
        review["tags"] = _loads_tags(review.get("tags"))
        review["action_taken"] = bool(review.get("action_taken"))
    return reviews


def create_review(payload: dict[str, Any]) -> dict:
    timestamp = now_iso()
    tags = payload.get("tags") or []
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reviews
                (date, stock_code, signal_id, action_taken, reason, result, summary, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["date"],
                payload["stock_code"],
                payload.get("signal_id"),
                1 if payload.get("action_taken") else 0,
                payload.get("reason", ""),
                payload.get("result", ""),
                payload.get("summary", ""),
                json.dumps(tags, ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
    return get_review(cursor.lastrowid) or {}


def update_review(review_id: int, payload: dict[str, Any]) -> dict | None:
    current = get_review(review_id)
    if not current:
        return None
    updated = {
        "date": payload.get("date", current["date"]),
        "stock_code": payload.get("stock_code", current["stock_code"]),
        "signal_id": payload.get("signal_id", current.get("signal_id")),
        "action_taken": payload.get("action_taken", current["action_taken"]),
        "reason": payload.get("reason", current["reason"]),
        "result": payload.get("result", current["result"]),
        "summary": payload.get("summary", current["summary"]),
        "tags": payload.get("tags", current["tags"]),
    }
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE reviews
            SET date = ?, stock_code = ?, signal_id = ?, action_taken = ?, reason = ?,
                result = ?, summary = ?, tags = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["date"],
                updated["stock_code"],
                updated["signal_id"],
                1 if updated["action_taken"] else 0,
                updated["reason"],
                updated["result"],
                updated["summary"],
                json.dumps(updated["tags"], ensure_ascii=False),
                now_iso(),
                review_id,
            ),
        )
    return get_review(review_id)


def delete_review(review_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    return cursor.rowcount > 0


def get_review(review_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*, s.name AS stock_name
            FROM reviews r
            JOIN stocks s ON s.code = r.stock_code
            WHERE r.id = ?
            """,
            (review_id,),
        ).fetchone()
    review = dict_from_row(row)
    if review:
        review["tags"] = _loads_tags(review.get("tags"))
        review["action_taken"] = bool(review.get("action_taken"))
    return review


def review_stats() -> dict:
    reviews = list_reviews(limit=1000)
    total = len(reviews)
    tag_counts: dict[str, int] = {}
    executed = sum(1 for review in reviews if review["action_taken"])
    for review in reviews:
        for tag in review["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return {
        "total": total,
        "executed": executed,
        "not_executed": total - executed,
        "tag_counts": tag_counts,
    }


def _loads_tags(raw: object) -> list[str]:
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        value = json.loads(str(raw))
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return [item.strip() for item in str(raw).split(",") if item.strip()]

