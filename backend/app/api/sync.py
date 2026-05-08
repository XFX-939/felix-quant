from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import task_service

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/failed-records")
def failed_records(
    task_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    return task_service.list_failed_sync_records(task_type=task_type, status=status, limit=limit)
