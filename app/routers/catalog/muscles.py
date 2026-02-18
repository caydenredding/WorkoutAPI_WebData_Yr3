from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models
from app.schemas.catalog import MuscleOut

router = APIRouter(prefix="/muscles")


@router.get(
    "",
    response_model=List[MuscleOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "List of muscles returned"},
    },
)
def list_muscles(db: Session = Depends(get_db)):
    return db.query(models.Muscle).order_by(models.Muscle.name).all()
