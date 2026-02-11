from fastapi import APIRouter

from .workouts import router as workouts_router
from .exercise_logs import router as exercise_logs_router
from .sets import router as sets_router

router = APIRouter(prefix="/training", tags=["training"])

router.include_router(workouts_router)
router.include_router(exercise_logs_router)
router.include_router(sets_router)
