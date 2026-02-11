from fastapi import APIRouter

from .analytics import router as analytics_router

router = APIRouter(prefix="/analytics", tags=["analytics"])

router.include_router(analytics_router)

