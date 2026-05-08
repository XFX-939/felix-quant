from fastapi import APIRouter, HTTPException, Query

from app.schemas.requests import ReviewPayload
from app.services.review_service import create_review, delete_review, list_reviews, review_stats, update_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def get_reviews(
    date: str | None = None,
    stock_code: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    return list_reviews(date=date, stock_code=stock_code, tag=tag, limit=limit)


@router.get("/stats")
def get_review_stats() -> dict:
    return review_stats()


@router.post("")
def post_review(payload: ReviewPayload) -> dict:
    return create_review(payload.model_dump())


@router.put("/{review_id}")
def put_review(review_id: int, payload: ReviewPayload) -> dict:
    review = update_review(review_id, payload.model_dump())
    if not review:
        raise HTTPException(status_code=404, detail="review not found")
    return review


@router.delete("/{review_id}")
def remove_review(review_id: int) -> dict:
    deleted = delete_review(review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="review not found")
    return {"deleted": True}

