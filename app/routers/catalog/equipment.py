from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models
from app.schemas.catalog import EquipmentOut

router = APIRouter(prefix="/equipment")


@router.get(
    "",
    response_model=List[EquipmentOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "List of equipment returned"},
    },
)
def list_equipment(db: Session = Depends(get_db)):
    return db.query(models.Equipment).order_by(models.Equipment.name).all()
