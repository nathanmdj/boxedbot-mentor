"""
Health check endpoints for monitoring and status
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.services.health_service import HealthService

router = APIRouter()
logger = get_logger(__name__)


@router.get("/")
async def basic_health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    
    Returns basic service status information.
    Used by load balancers and monitoring systems for quick health checks.
    """
    try:
        health_service = HealthService()
        return await health_service.basic_health_check()
        
    except Exception as e:
        logger.error(f"Basic health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check endpoint
    
    Returns comprehensive health information including:
    - Service status
    - Dependency status (GitHub API, OpenAI API)
    - Response times
    - System metrics
    """
    try:
        health_service = HealthService()
        return await health_service.detailed_health_check()
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@router.get("/dependencies")
async def check_dependencies() -> Dict[str, Any]:
    """
    Check external dependencies
    
    Verifies connectivity and status of:
    - GitHub API
    - OpenAI API
    """
    try:
        health_service = HealthService()
        return await health_service.check_dependencies()
        
    except Exception as e:
        logger.error(f"Dependencies check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e)
            }
        )


@router.get("/metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """
    Get system metrics
    
    Returns system metrics and configuration information
    for monitoring and debugging purposes.
    """
    try:
        health_service = HealthService()
        return await health_service.get_system_metrics()
        
    except Exception as e:
        logger.error(f"System metrics failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e)
            }
        )


@router.get("/status")
async def service_status() -> Dict[str, Any]:
    """
    Service status endpoint
    
    Returns current service status with minimal overhead.
    Alternative to basic health check for simple monitoring.
    """
    from app.core.config import settings
    import time
    
    return {
        "service": "boxedbot",
        "status": "running",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time()
    }