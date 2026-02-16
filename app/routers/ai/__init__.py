from fastapi import APIRouter

from .summaries import router as summaries_router

router = APIRouter(prefix="/ai", tags=["ai"])

router.include_router(summaries_router)