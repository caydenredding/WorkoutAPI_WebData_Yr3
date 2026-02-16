from fastapi import APIRouter

from .exercises import router as exercises_router
from .muscles import router as muscles_router
from .equipment import router as equipment_router
from .goals import router as goals_router

router = APIRouter(prefix="/catalog", tags=["catalog"])

router.include_router(exercises_router)
router.include_router(muscles_router)
router.include_router(equipment_router)
router.include_router(goals_router)