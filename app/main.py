from fastapi import FastAPI

from app.routers.training import router as training_router
from app.routers.catalog import router as catalog_router
from app.routers.users import router as users_router
from app.routers.analytics import router as analytics_router

app = FastAPI(
    title="Gym API",
    version="0.1.0",
)

app.include_router(training_router)
app.include_router(catalog_router)
app.include_router(users_router)
app.include_router(analytics_router)


@app.get(
    "/health",
    tags=["health"],
)
def health():
    return {"status": "ok"}
