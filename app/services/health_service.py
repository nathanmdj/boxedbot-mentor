"""
Health check service for monitoring system dependencies
"""

import asyncio
import time
from typing import Dict, Any, Optional
import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.services.github_service import GitHubService


class HealthService(LoggerMixin):
    """Service for health checks and monitoring"""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def basic_health_check(self) -> Dict[str, Any]:
        """Basic health check for the service"""
        return {
            "status": "healthy",
            "service": "boxedbot",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": time.time()
        }
    
    async def detailed_health_check(self) -> Dict[str, Any]:
        """Detailed health check including dependencies"""
        start_time = time.time()
        
        try:
            # Run all health checks concurrently
            github_check, openai_check = await asyncio.gather(
                self._check_github_api(),
                self._check_openai_api(),
                return_exceptions=True
            )
            
            # Process results
            dependencies = {
                "github_api": self._format_check_result(github_check),
                "openai_api": self._format_check_result(openai_check)
            }
            
            # Determine overall status
            overall_status = "healthy"
            if any(dep["status"] == "unhealthy" for dep in dependencies.values()):
                overall_status = "unhealthy"
            elif any(dep["status"] == "degraded" for dep in dependencies.values()):
                overall_status = "degraded"
            
            total_time = time.time() - start_time
            
            return {
                "status": overall_status,
                "service": "boxedbot",
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "timestamp": time.time(),
                "check_duration_seconds": round(total_time, 3),
                "dependencies": dependencies
            }
            
        except Exception as e:
            self.log_error("Detailed health check", e)
            return {
                "status": "unhealthy",
                "service": "boxedbot",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def _check_github_api(self) -> Dict[str, Any]:
        """Check GitHub API connectivity"""
        start_time = time.time()
        
        try:
            # Simple API call to check connectivity
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.GITHUB_API_URL}/rate_limit",
                    headers={
                        "Authorization": f"Bearer {self.github_service.get_jwt_token()}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )
            
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                rate_limit_data = response.json()
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time * 1000, 2),
                    "rate_limit": rate_limit_data.get("rate", {})
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time_ms": round(response_time * 1000, 2),
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200]
                }
                
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time * 1000, 2),
                "error": str(e)
            }
    
    async def _check_openai_api(self) -> Dict[str, Any]:
        """Check OpenAI API connectivity"""
        start_time = time.time()
        
        try:
            # Simple API call to check connectivity
            models = await self.openai_client.models.list()
            
            response_time = time.time() - start_time
            
            # Check if our required models are available
            available_models = [model.id for model in models.data]
            required_models = [settings.OPENAI_MODEL_SMALL, settings.OPENAI_MODEL_LARGE]
            missing_models = [model for model in required_models if model not in available_models]
            
            if missing_models:
                return {
                    "status": "degraded",
                    "response_time_ms": round(response_time * 1000, 2),
                    "warning": f"Missing models: {missing_models}",
                    "available_models": len(available_models)
                }
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "available_models": len(available_models),
                "required_models_available": True
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time * 1000, 2),
                "error": str(e)
            }
    
    def _format_check_result(self, result: Any) -> Dict[str, Any]:
        """Format health check result"""
        if isinstance(result, Exception):
            return {
                "status": "unhealthy",
                "error": str(result),
                "last_check": time.time()
            }
        elif isinstance(result, dict):
            result["last_check"] = time.time()
            return result
        else:
            return {
                "status": "unknown",
                "error": f"Unexpected result type: {type(result)}",
                "last_check": time.time()
            }
    
    async def check_dependencies(self) -> Dict[str, Any]:
        """Check all dependencies and return status"""
        try:
            detailed_check = await self.detailed_health_check()
            return {
                "overall_status": detailed_check["status"],
                "dependencies": detailed_check["dependencies"],
                "timestamp": detailed_check["timestamp"]
            }
            
        except Exception as e:
            self.log_error("Dependencies check", e)
            return {
                "overall_status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics for monitoring"""
        try:
            # Basic system information
            metrics = {
                "service": "boxedbot",
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "timestamp": time.time(),
                "uptime_seconds": self._get_uptime_seconds(),
                "configuration": {
                    "max_comments_per_pr": settings.MAX_COMMENTS_PER_PR,
                    "small_pr_threshold": settings.SMALL_PR_THRESHOLD,
                    "medium_pr_threshold": settings.MEDIUM_PR_THRESHOLD,
                    "ai_models": {
                        "small": settings.OPENAI_MODEL_SMALL,
                        "large": settings.OPENAI_MODEL_LARGE
                    }
                }
            }
            
            return metrics
            
        except Exception as e:
            self.log_error("System metrics", e)
            return {
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _get_uptime_seconds(self) -> float:
        """Get service uptime in seconds"""
        # In a real implementation, this would track when the service started
        # For now, return a placeholder
        return 3600.0  # 1 hour placeholder