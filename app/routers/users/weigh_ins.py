from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas.users import WeighInCreate, WeighInOut, WeighInUpdate, WeighInListOut
from app.security import require_self_or_admin, get_current_user

router = APIRouter()


@router.post(
    "/{user_id}/weigh-ins",
    response_model=WeighInOut,
    status_code=status.HTTP_201_CREATED,
)
def create_weigh_in(
    user_id: int,
    payload: WeighInCreate,
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
):
    user_exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not user_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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
    response_model=WeighInOut,
    status_code=status.HTTP_200_OK,
)
def get_weigh_in(
    weigh_in_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    weigh_in = db.query(models.WeighIn).filter(models.WeighIn.id == weigh_in_id).first()
    if not weigh_in:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weigh-in not found")

    # Authorise: owner or admin
    if current_user.role != "admin" and weigh_in.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    return weigh_in


@router.get(
    "/{user_id}/weigh-ins",
    response_model=WeighInListOut,
    status_code=status.HTTP_200_OK,
)
def get_recent_weigh_ins(
    user_id: int,
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
    limit: int = Query(5, ge=1, le=100, description="Number of most recent weigh-ins to return"),
):
    user_exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not user_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    weigh_ins = (
        db.query(models.WeighIn)
        .filter(models.WeighIn.user_id == user_id)
        .order_by(models.WeighIn.date.desc())
        .limit(limit)
        .all()
    )

    weigh_ins = list(reversed(weigh_ins))

    return {"user_id": user_id, "count": len(weigh_ins), "weigh_ins": weigh_ins}


@router.patch(
    "/weigh-ins/{weigh_in_id}",
    response_model=WeighInOut,
    status_code=status.HTTP_200_OK,
)
def update_weigh_in(
    weigh_in_id: int,
    payload: WeighInUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    weigh_in = db.query(models.WeighIn).filter(models.WeighIn.id == weigh_in_id).first()
    if not weigh_in:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weigh-in not found")

    if current_user.role != "admin" and weigh_in.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    for field, value in update_data.items():
        setattr(weigh_in, field, value)

    db.commit()
    db.refresh(weigh_in)
    return weigh_in


@router.delete(
    "/weigh-ins/{weigh_in_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_weigh_in(
    weigh_in_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    weigh_in = db.query(models.WeighIn).filter(models.WeighIn.id == weigh_in_id).first()
    if not weigh_in:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weigh-in not found")

    if current_user.role != "admin" and weigh_in.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    db.delete(weigh_in)
    db.commit()
    return