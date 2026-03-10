from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.insights import SignalsResponse
from app.services.insights.insights import get_signals_response
from app.security import require_api_key, require_self_or_admin

router = APIRouter()


@router.get(
    "/users/{user_id}/signals",
    response_model=SignalsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_api_key)],
)
def get_signals(
    user_id: int,
    as_of: date = Query(..., description="Evaluate state as of this date"),
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
):
    return get_signals_response(db, user_id, as_of)