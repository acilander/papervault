from fastapi import APIRouter, HTTPException

from db import feedback_repo

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/")
def list_feedback():
    return feedback_repo.get_all()


@router.delete("/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: int):
    feedback_repo.delete(feedback_id)
    return None
