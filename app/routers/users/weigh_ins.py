from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter()

@router.post(
    "/{user_id}/weigh-ins",
    response_model=schemas.WeighInOut,
)
def create_weigh_in(user_id: int, payload: schemas.WeighInCreate, db: Session = Depends(get_db)):

    weigh_in = models.WeighIn(
        user_id=user_id,
        weight=payload.weight,
        date=payload.date,
    )

    db.add(weigh_in)
    db.commit()
    db.refresh(weigh_in)

    return weigh_in

@router.get(
    "/weigh-ins/{weigh_in_id}",
    response_model=schemas.WeighInOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Weigh-in retrieved"},
        status.HTTP_404_NOT_FOUND: {"description": "Weigh-in not found"},
    },
)
def get_weigh_in(
    weigh_in_id: int,
    db: Session = Depends(get_db),
):
    weigh_in = (
        db.query(models.WeighIn)
        .filter(models.WeighIn.id == weigh_in_id)
        .first()
    )

    if not weigh_in:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weigh-in not found",
        )

    return weigh_in

@router.get(
    "/{user_id}/weigh-ins",
    response_model=schemas.WeighInListOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Most recent weigh-ins returned"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def get_recent_weigh_ins(
    user_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(
        5,
        ge=1,
        le=100,
        description="Number of most recent weigh-ins to return",
    ),
):
    # Ensure user exists
    user_exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    weigh_ins = (
        db.query(models.WeighIn)
        .filter(models.WeighIn.user_id == user_id)
        .order_by(models.WeighIn.date.desc())
        .limit(limit)
        .all()
    )

    # Optional: reverse to chronological order (oldest -> newest)
    weigh_ins = list(reversed(weigh_ins))

    return {
        "user_id": user_id,
        "count": len(weigh_ins),
        "weigh_ins": weigh_ins,
    }
    
@router.patch(
    "/weigh-ins/{weigh_in_id}",
    response_model=schemas.WeighInOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Weigh-in successfully updated"},
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update"},
        status.HTTP_404_NOT_FOUND: {"description": "Weigh-in not found"},
    },
)
def update_weigh_in(
    weigh_in_id: int,
    payload: schemas.WeighInUpdate,
    db: Session = Depends(get_db),
):
    weigh_in = db.query(models.WeighIn).filter(models.WeighIn.id == weigh_in_id).first()
    if not weigh_in:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weigh-in not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    for field, value in update_data.items():
        setattr(weigh_in, field, value)

    db.commit()
    db.refresh(weigh_in)
    return weigh_in

@router.delete(
    "/weigh-ins/{weigh_in_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Weigh-in successfully deleted"},
        status.HTTP_404_NOT_FOUND: {"description": "Weigh-in not found"},
    },
)
def delete_weigh_in(
    weigh_in_id: int,
    db: Session = Depends(get_db),
):
    weigh_in = (
        db.query(models.WeighIn)
        .filter(models.WeighIn.id == weigh_in_id)
        .first()
    )

    if not weigh_in:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weigh-in not found",
        )

    db.delete(weigh_in)
    db.commit()

    return
