from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter()

@router.get("", response_model=list[schemas.MuscleOut])
def list_muscles(db: Session = Depends(get_db)):
    return db.query(models.Muscle).order_by(models.Muscle.name).all()
