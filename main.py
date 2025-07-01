"""
BoxedBot - AI-Powered PR Reviewer
Main Modal application entry point
"""

import os
import modal
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import os

# Set development environment for local testing
os.environ.setdefault("ENVIRONMENT", "development")

from app.core.config import settings
from app.api.routes import api_router
from app.core.logging import setup_logging

# Setup logging
logger = setup_logging()

# Create Modal app
app = modal.App(settings.APP_NAME)

# Define container image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi==0.104.1",
        "uvicorn==0.24.0",
        "openai==1.3.8",
        "PyGithub==1.59.1",
        "python-jose[cryptography]==3.3.0",
        "pydantic==2.5.0",
        "pydantic-settings==2.1.0",
        "httpx==0.25.2",
        "pyyaml==6.0.1",
        "tenacity==8.2.3",
        "python-multipart==0.0.6"
    )
    .add_local_dir("app", "/root/app")
)

# Create FastAPI app
def create_fastapi_app() -> FastAPI:
    """Create and configure FastAPI application"""
    # Force enable docs for development
    enable_docs = settings.DEBUG or settings.ENVIRONMENT == "development"
    
    fastapi_app = FastAPI(
        title=settings.APP_NAME,
        description="AI-Powered GitHub PR Reviewer",
        version=settings.VERSION,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None
    )
    
    # Add CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    fastapi_app.include_router(api_router, prefix="/api/v1")
    
    # Global exception handler
    @fastapi_app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )
    
    return fastapi_app

# Create FastAPI instance
web_app = create_fastapi_app()

# Mount FastAPI app to Modal
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("github-app-secrets"),
        modal.Secret.from_name("openai-secrets")
    ],
    timeout=300,
    memory=1024
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    """Modal ASGI app wrapper"""
    return web_app

# Background function for PR analysis
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("github-app-secrets"),
        modal.Secret.from_name("openai-secrets")
    ],
    timeout=600,  # 10 minutes for complex analysis
    memory=2048,  # 2GB for AI processing
    retries=modal.Retries(
        max_retries=3,
        backoff_coefficient=2.0,
        initial_delay=1.0
    )
)
async def analyze_pr_background(pr_data: dict) -> dict:
    """Background function for PR analysis"""
    from app.services.pr_analyzer import PRAnalyzerService
    
    try:
        logger.info(f"Starting PR analysis for PR #{pr_data.get('pr_number')}")
        
        analyzer = PRAnalyzerService()
        result = await analyzer.analyze_pr_async(pr_data)
        
        logger.info(f"Completed PR analysis for PR #{pr_data.get('pr_number')}")
        return {"status": "completed", "result": result}
        
    except Exception as e:
        logger.error(f"Failed to analyze PR #{pr_data.get('pr_number')}: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}

# Health check function
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("github-app-secrets"),
        modal.Secret.from_name("openai-secrets")
    ],
    timeout=30
)
async def health_check_background() -> dict:
    """Background health check for dependencies"""
    from app.services.health_service import HealthService
    
    health_service = HealthService()
    return await health_service.check_dependencies()

if __name__ == "__main__":
    # For local development
    import uvicorn
    uvicorn.run("main:web_app", host="0.0.0.0", port=8000, reload=True)