from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.insights import InsightsResponse
from app.services.insights.insights import get_insights_response
from app.security import require_api_key, require_self_or_admin

router = APIRouter()


@router.get(
    "/users/{user_id}/insights",
    response_model=InsightsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_api_key)],
)
def get_insights(
    user_id: int,
    as_of: date = Query(..., description="Evaluate state as of this date"),
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
):
    return get_insights_response(db, user_id, as_of)