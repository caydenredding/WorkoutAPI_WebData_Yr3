from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models

from app.schemas.catalog import GoalOut

router = APIRouter(prefix="/goals")


@router.get(
    "/",
    response_model=List[GoalOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "List of goals returned"},
    },
)
def list_goals(db: Session = Depends(get_db)):
    return db.query(models.Goal).order_by(models.Goal.name.asc()).all()
