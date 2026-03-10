from fastapi import FastAPI

from app.routers.training import router as training_router
from app.routers.catalog import router as catalog_router
from app.routers.users import router as users_router
from app.routers.analytics import router as analytics_router
from app.routers.insights import router as insights_router
from app.routers.auth import router as auth_router
from app.routers.me import router as me_router

app = FastAPI(
    title="Gym Training Analytics API",
    description="""
REST API for tracking gym workouts, analysing training metrics,
and generating personalised training insights.

Features include:
- Workout logging
- Exercise performance analytics
- Training adherence metrics
- AI-style training insights
- Role-based access control
""",
    version="1.2.0",
)

app.include_router(auth_router)
app.include_router(me_router)

app.include_router(training_router)
app.include_router(catalog_router)
app.include_router(users_router)
app.include_router(analytics_router)
app.include_router(insights_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}