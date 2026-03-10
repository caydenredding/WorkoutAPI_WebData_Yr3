from fastapi import APIRouter

from .me import router as me_router

router = APIRouter(prefix="/me", tags=["me"])

router.include_router(me_router)