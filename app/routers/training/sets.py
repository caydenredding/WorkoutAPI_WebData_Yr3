from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models
from app.schemas.training import SetCreate, SetOut, SetUpdate

router = APIRouter(prefix="/sets")


@router.post(
    "/exercise-logs/{exercise_log_id}",
    response_model=SetOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {"description": "Set successfully created"},
        status.HTTP_404_NOT_FOUND: {"description": "Exercise log not found"},
    },
)
def create_set(
    exercise_log_id: int,
    payload: SetCreate,
    db: Session = Depends(get_db),
):
    log = db.query(models.ExerciseLog).filter(models.ExerciseLog.id == exercise_log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise log not found",
        )

    s = models.SetLog(
        exercise_log_id=exercise_log_id,
        reps=payload.reps,
        weight=payload.weight,
        rir=payload.rir,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get(
    "/exercise-logs/{exercise_log_id}",
    response_model=List[SetOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "List of sets returned"},
        status.HTTP_404_NOT_FOUND: {"description": "Exercise log not found"},
    },
)
def list_sets(
    exercise_log_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    log_exists = db.query(models.ExerciseLog.id).filter(models.ExerciseLog.id == exercise_log_id).first()
    if not log_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise log not found",
        )

    return (
        db.query(models.SetLog)
        .filter(models.SetLog.exercise_log_id == exercise_log_id)
        .order_by(models.SetLog.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.patch(
    "/{set_id}",
    response_model=SetOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Set successfully updated"},
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update"},
        status.HTTP_404_NOT_FOUND: {"description": "Set not found"},
    },
)
def update_set(
    set_id: int,
    payload: SetUpdate,
    db: Session = Depends(get_db),
):
    s = db.query(models.SetLog).filter(models.SetLog.id == set_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Set not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    for field, value in update_data.items():
        setattr(s, field, value)

    db.commit()
    db.refresh(s)
    return s


@router.delete(
    "/{set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Set successfully deleted"},
        status.HTTP_404_NOT_FOUND: {"description": "Set not found"},
    },
)
def delete_set(
    set_id: int,
    db: Session = Depends(get_db),
):
    s = db.query(models.SetLog).filter(models.SetLog.id == set_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Set not found",
        )

    db.delete(s)
    db.commit()
    return
