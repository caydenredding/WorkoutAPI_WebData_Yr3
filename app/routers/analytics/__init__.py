# app/routers/analytics/__init__.py
from fastapi import APIRouter

from .exercise_metrics import router as exercise_metrics_router
from .adherence import router as adherence_router

router = APIRouter(prefix="/analytics", tags=["analytics"])
router.include_router(exercise_metrics_router)
router.include_router(adherence_router)
