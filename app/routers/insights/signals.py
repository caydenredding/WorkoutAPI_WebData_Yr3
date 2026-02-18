from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.insights import SignalsResponse
from app.services.insights.insights import get_signals_response

router = APIRouter()

@router.get(
    "/users/{user_id}/signals",
    response_model=SignalsResponse,
    status_code=status.HTTP_200_OK,
)
def get_signals(
    user_id: int,
    as_of: date = Query(..., description="Evaluate state as of this date"),
    db: Session = Depends(get_db),
):
    return get_signals_response(db, user_id, as_of)
