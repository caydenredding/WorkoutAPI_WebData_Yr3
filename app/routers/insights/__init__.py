from fastapi import APIRouter
from .signals import router as signals_router
from .insights import router as insights_router

router = APIRouter(tags=["Insights"])
router.include_router(signals_router)
router.include_router(insights_router)
