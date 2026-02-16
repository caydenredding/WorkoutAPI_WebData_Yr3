from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.ai.summary_facts import build_weekly_facts

router = APIRouter(tags=["ai"])

@router.get(
    "/users/{user_id}/summaries/weekly/facts",
    status_code=status.HTTP_200_OK,
)
def weekly_facts(
    user_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    num_facts: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return build_weekly_facts(db, user_id, date_from, date_to, top_prs_count=num_facts)