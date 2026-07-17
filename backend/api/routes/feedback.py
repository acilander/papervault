from fastapi import APIRouter, HTTPException

from db import feedback_repo

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/")
def list_feedback():
    return feedback_repo.get_all()


@router.get("/coverage")
def get_feedback_coverage():
    """Get metrics about category and document type training coverage in feedback."""
    return feedback_repo.get_coverage_stats()


@router.delete("/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: int):
    feedback_repo.delete(feedback_id)
    return None
