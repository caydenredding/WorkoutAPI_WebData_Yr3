from fastapi import APIRouter

from .users import router as users_router
from .weigh_ins import router as weigh_ins_router

router = APIRouter(prefix="/users", tags=["users"])

router.include_router(users_router)
router.include_router(weigh_ins_router)
