"""
Main API router that combines all endpoint modules
"""

from fastapi import APIRouter

from app.api.endpoints import webhooks, health, config

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["webhooks"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    config.router,
    prefix="/config",
    tags=["configuration"]
)