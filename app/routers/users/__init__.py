from fastapi import APIRouter

from .users import router as users_router

router = APIRouter(prefix="/users", tags=["users"])

router.include_router(users_router)
